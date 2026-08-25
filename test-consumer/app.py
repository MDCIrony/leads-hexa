"""Nordwind Solar's own inbox: what a customer of the lead router would build.

Deliberately independent of `backend/` (ADR-0026). It imports nothing from the
product, speaks only its published contracts — the Kafka topic and, for
catching up, GET /leads with an X-Api-Key — and keeps its own database. If this
app needed anything from the product's source to work, the contract would not
stand on its own.

Two doors in, on purpose:
  · Kafka  — every lead as it is routed, live.
  · HTTP   — GET /leads?updated_since=…, to fill a gap without replaying.
"""
import json
import logging
import os
import sqlite3
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from confluent_kafka import Consumer, KafkaException
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

LOGGER = logging.getLogger("inbox")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

DB_PATH = Path(os.getenv("INBOX_DB", "/data/inbox.db"))
# The address the credential reports is the public one; a client on the same
# network needs one that resolves here. Both point at the same broker and the
# same per-tenant ACLs decide what either may read.
BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9095")
API_BASE = os.getenv("LEADS_API_BASE", "http://backend:8000/api/v1")

WORK_STATES = ["PENDIENTE", "CONTACTADO", "PROPUESTA", "GANADO", "PERDIDO"]

_lock = threading.Lock()


# ------------------------------------------------------------------ store ---

@contextmanager
def db():
    """One connection per call. SQLite objects are bound to the thread that
    created them, and the Kafka consumer runs in a different one from the API."""
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS leads (
                lead_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                arrived_by TEXT NOT NULL,
                received_at TEXT NOT NULL,
                first_name TEXT DEFAULT '',
                last_name TEXT DEFAULT '',
                email TEXT,
                phone TEXT,
                company TEXT DEFAULT '',
                industry TEXT DEFAULT '',
                budget TEXT DEFAULT '',
                score INTEGER DEFAULT 0,
                router_status TEXT DEFAULT '',
                assigned_agent_id TEXT,
                assigned_at TEXT,
                reason TEXT DEFAULT '',
                payload TEXT NOT NULL,
                work_state TEXT NOT NULL DEFAULT 'PENDIENTE',
                owner TEXT NOT NULL DEFAULT '',
                notes TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS deliveries (
                event_id TEXT PRIMARY KEY,
                seen_at TEXT NOT NULL
            );
        """)


def setting(key: str, default: Optional[str] = None) -> Optional[str]:
    with db() as connection:
        row = connection.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def put_setting(key: str, value: str) -> None:
    with db() as connection:
        connection.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def credential() -> Optional[Dict[str, Any]]:
    raw = setting("credential")
    return json.loads(raw) if raw else None


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------------------- ingestion ---

def store_event(payload: Dict[str, Any], event_type: str, arrived_by: str) -> bool:
    """Upsert one lead, keeping whatever this office has already written on it.

    Delivery is at-least-once: the same event arrives twice whenever a consumer
    restarts before committing. Overwriting work_state, owner and notes on the
    second copy would quietly undo an advisor's afternoon, so the update names
    only the fields the router owns."""
    lead_id = payload.get("lead_id")
    if not lead_id:
        return False

    event_id = payload.get("event_id")
    with _lock, db() as connection:
        if event_id:
            seen = connection.execute(
                "SELECT 1 FROM deliveries WHERE event_id = ?", (event_id,)
            ).fetchone()
            if seen:
                return False
            connection.execute(
                "INSERT INTO deliveries (event_id, seen_at) VALUES (?, ?)", (event_id, now())
            )
        connection.execute(
            """
            INSERT INTO leads (
                lead_id, event_type, arrived_by, received_at, first_name, last_name,
                email, phone, company, industry, budget, score, router_status,
                assigned_agent_id, assigned_at, reason, payload, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(lead_id) DO UPDATE SET
                event_type = excluded.event_type,
                arrived_by = excluded.arrived_by,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                email = excluded.email,
                phone = excluded.phone,
                company = excluded.company,
                industry = excluded.industry,
                budget = excluded.budget,
                score = excluded.score,
                router_status = excluded.router_status,
                assigned_agent_id = excluded.assigned_agent_id,
                assigned_at = excluded.assigned_at,
                reason = excluded.reason,
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (
                lead_id, event_type, arrived_by, now(),
                payload.get("first_name", ""), payload.get("last_name", ""),
                payload.get("email"), payload.get("phone"),
                payload.get("company", ""), payload.get("industry", ""),
                str(payload.get("budget", "")), int(payload.get("score") or 0),
                payload.get("status", ""), payload.get("assigned_agent_id"),
                payload.get("assigned_at"), payload.get("reason", ""),
                json.dumps(payload, ensure_ascii=False), now(),
            ),
        )
    return True


# ------------------------------------------------------------- consumer ---

class KafkaListener:
    """The Kafka half, in a thread of its own.

    Restartable because `replay` is a demonstration in itself: the point of a
    log with retention is that a consumer who lost its database can read the
    week back, which no queue can do."""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.state = "detenido"
        self.error: Optional[str] = None
        self.consumed = 0
        self.last_message_at: Optional[str] = None

    def start(self, from_beginning: bool = False) -> None:
        self.stop()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(from_beginning,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=8)
        self._thread = None
        self.state = "detenido"

    def _run(self, from_beginning: bool) -> None:
        cred = credential()
        if not cred:
            self.state, self.error = "sin credencial", "todavía no se ha registrado"
            return
        # A fresh group id whenever we replay: reusing it would resume from the
        # committed offset and the replay would return nothing.
        suffix = uuid.uuid4().hex[:8] if from_beginning else "inbox"
        config = {
            "bootstrap.servers": BOOTSTRAP,
            "security.protocol": "SASL_PLAINTEXT",
            "sasl.mechanism": "SCRAM-SHA-256",
            "sasl.username": cred["kafka_username"],
            "sasl.password": cred["kafka_password"],
            # Must start with the principal itself: the broker's ACL grants
            # this tenant only its own group prefix, and any other name is
            # refused with GROUP_AUTHORIZATION_FAILED.
            "group.id": f"{cred['kafka_username']}-{suffix}",
            "auto.offset.reset": "earliest" if from_beginning else "latest",
            "enable.auto.commit": True,
        }
        consumer = Consumer(config)
        try:
            consumer.subscribe([cred["kafka_topic"]])
            self.state, self.error = "escuchando", None
            while not self._stop.is_set():
                message = consumer.poll(1.0)
                if message is None:
                    continue
                if message.error():
                    self.error = str(message.error())
                    LOGGER.warning("kafka: %s", self.error)
                    continue
                headers = dict(message.headers() or [])
                event_type = headers.get("event_type", b"?").decode()
                try:
                    payload = json.loads(message.value())
                except ValueError:
                    self.error = "un mensaje no era JSON"
                    continue
                if store_event(payload, event_type, "kafka"):
                    self.consumed += 1
                self.last_message_at = now()
        except KafkaException as error:
            self.state, self.error = "error", str(error)
            LOGGER.exception("el consumidor se ha caído")
        finally:
            consumer.close()
            if self.state != "error":
                self.state = "detenido"


listener = KafkaListener()


# ------------------------------------------------------------------- api ---

def call_api(method: str, path: str, *, token=None, api_key=None, form=None, timeout=20):
    url = f"{API_BASE}{path}"
    headers = {}
    data = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["X-Api-Key"] = api_key
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, {"detail": raw.decode(errors="replace")}
    except urllib.error.URLError as error:
        raise HTTPException(502, f"no se alcanza {url}: {error.reason}")


app = FastAPI(title="Bandeja de Nordwind Solar", docs_url="/api/docs")
init_db()


@app.on_event("startup")
def resume_listening() -> None:
    """Registration survives a restart, so listening has to as well."""
    if credential():
        listener.start()


class Registration(BaseModel):
    email: str
    password: str


@app.post("/api/register")
def register(body: Registration):
    """What an integrator does once: get a key for the machine, not for a person.

    Two calls to the product, both of them public contract: log in as the
    manager who authorises the integration, then ask for the credential. The
    manager's password is never stored — only the credential that comes back."""
    status, data = call_api("POST", "/auth/login", form={"username": body.email, "password": body.password})
    if status != 200 or not data.get("access_token"):
        raise HTTPException(401, "usuario o contraseña incorrectos para el router de leads")

    status, credential_data = call_api("POST", "/agents/integration-credential", token=data["access_token"])
    if status != 201:
        raise HTTPException(status, f"el router no emitió la credencial: {credential_data}")

    put_setting("credential", json.dumps(credential_data))
    put_setting("registered_at", now())
    listener.start()
    return {"tenant_id": credential_data["tenant_id"], "topic": credential_data["kafka_topic"]}


@app.post("/api/forget")
def forget():
    listener.stop()
    with db() as connection:
        connection.execute("DELETE FROM settings WHERE key IN ('credential', 'registered_at')")
    return {"ok": True}


@app.get("/api/status")
def status():
    cred = credential()
    with db() as connection:
        total = connection.execute("SELECT COUNT(*) AS n FROM leads").fetchone()["n"]
        by_state = {
            row["work_state"]: row["n"]
            for row in connection.execute(
                "SELECT work_state, COUNT(*) AS n FROM leads WHERE event_type <> 'LeadDisqualified' GROUP BY work_state"
            )
        }
        discarded = connection.execute(
            "SELECT COUNT(*) AS n FROM leads WHERE event_type = 'LeadDisqualified'"
        ).fetchone()["n"]
    return {
        "registered": cred is not None,
        "tenant_id": cred["tenant_id"] if cred else None,
        "topic": cred["kafka_topic"] if cred else None,
        "bootstrap": BOOTSTRAP,
        "api_base": API_BASE,
        "listener": listener.state,
        "listener_error": listener.error,
        "consumed": listener.consumed,
        "last_message_at": listener.last_message_at,
        "total": total,
        "by_state": by_state,
        "discarded": discarded,
        "work_states": WORK_STATES,
    }


@app.get("/api/leads")
def list_leads(state: Optional[str] = None, q: Optional[str] = None, kind: str = "assigned"):
    clauses: List[str] = []
    params: List[Any] = []
    if kind == "discarded":
        clauses.append("event_type = 'LeadDisqualified'")
    else:
        clauses.append("event_type <> 'LeadDisqualified'")
    if state:
        clauses.append("work_state = ?")
        params.append(state)
    if q:
        clauses.append("(company LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR email LIKE ?)")
        params.extend([f"%{q}%"] * 4)
    sql = f"SELECT * FROM leads WHERE {' AND '.join(clauses)} ORDER BY score DESC, received_at DESC LIMIT 500"
    with db() as connection:
        rows = [dict(row) for row in connection.execute(sql, params)]
    return {"items": rows, "total": len(rows)}


class WorkUpdate(BaseModel):
    work_state: Optional[str] = None
    owner: Optional[str] = None
    notes: Optional[str] = None


@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: str, body: WorkUpdate):
    if body.work_state and body.work_state not in WORK_STATES:
        raise HTTPException(400, f"estado desconocido: {body.work_state}")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "nada que cambiar")
    assignments = ", ".join(f"{name} = ?" for name in fields)
    with db() as connection:
        cursor = connection.execute(
            f"UPDATE leads SET {assignments}, updated_at = ? WHERE lead_id = ?",
            [*fields.values(), now(), lead_id],
        )
        if cursor.rowcount == 0:
            raise HTTPException(404, "ese lead no está en esta bandeja")
        row = dict(connection.execute("SELECT * FROM leads WHERE lead_id = ?", (lead_id,)).fetchone())
    return row


@app.delete("/api/leads/{lead_id}", status_code=204)
def delete_lead(lead_id: str):
    with db() as connection:
        cursor = connection.execute("DELETE FROM leads WHERE lead_id = ?", (lead_id,))
        if cursor.rowcount == 0:
            raise HTTPException(404, "ese lead no está en esta bandeja")


@app.post("/api/replay")
def replay():
    """Read the topic from the beginning. What a queue cannot offer: the
    messages are still there after being consumed, for as long as retention."""
    if not credential():
        raise HTTPException(400, "hay que registrarse primero")
    listener.start(from_beginning=True)
    return {"ok": True}


@app.post("/api/resync")
def resync(since: Optional[str] = Body(default=None, embed=True)):
    """The other door: ask the API what changed, instead of replaying the log.

    Uses the machine credential, never a person's session — that is the whole
    point of X-Api-Key."""
    cred = credential()
    if not cred:
        raise HTTPException(400, "hay que registrarse primero")
    cursor = since or setting("resync_cursor") or "1970-01-01T00:00:00Z"

    # Paged until the API says there is no more. Stopping at the first page
    # would report a clean reconciliation while quietly leaving rows behind,
    # which is the one thing this button exists to rule out.
    items, offset = [], 0
    while True:
        query = urllib.parse.urlencode(
            {"updated_since": cursor, "limit": 500, "offset": offset}
        )
        http_status, page = call_api("GET", f"/leads?{query}", api_key=cred["api_key"])
        if http_status != 200:
            raise HTTPException(http_status, f"el router respondió {http_status}: {page}")
        items.extend(page.get("items", []))
        if not page.get("has_more"):
            break
        offset += 500

    # The server's own clock, not ours: `updated_since` filters on this very
    # field, so advancing the cursor to the newest value we were given cannot
    # skip a row over clock skew. The filter is inclusive, so the boundary rows
    # arrive once more next time — which the upsert absorbs.
    next_cursor = max((lead["updated_at"] for lead in items), default=None) or now()

    stored = 0
    for lead in items:
        # No event_id on an HTTP row: it is a snapshot, not an event, so the
        # de-duplication table cannot apply and the upsert carries the work.
        lead.pop("event_id", None)
        # GET /leads answers with the whole pipeline; the topic only carries
        # what the router kept, and says what it filtered in a different event.
        # Reading the status here is what keeps the two doors agreeing on which
        # tray a lead belongs in.
        event_type = (
            "LeadDisqualified" if lead.get("status") == "DISQUALIFIED" else "LeadProcessedEvent"
        )
        if store_event({**lead, "lead_id": lead["id"]}, event_type, "http"):
            stored += 1
    put_setting("resync_cursor", next_cursor)
    return {"desde": cursor, "recibidos": len(items), "guardados": stored}


app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

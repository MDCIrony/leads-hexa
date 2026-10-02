#!/usr/bin/env python3
"""Fills a running stack with one company big enough to see routing work.

Only the standard library: this runs on the host against http://localhost:8001,
and asking whoever follows the demo to install anything first is one more way
for the demo to fail before it starts.

Re-running is safe. Every entity is looked up before it is created, so a second
run reports what already existed instead of colliding on the unique email.

    python3 demo/seed.py                 # against the default stack
    python3 demo/seed.py --api http://…  # somewhere else
"""
import argparse
import json
import sys
from pathlib import Path

from api_client import Api, die

PASSWORD = "Demo1234"
COMPANY = "Nordwind Solar"
DOMAIN = "nordwindsolar.test"
MANAGER_EMAIL = f"gestor@{DOMAIN}"
PLATFORM_ADMIN = ("root@plat.test", "Secret123")

# Four per group, so a round-robin rotation is visible and a lowest-load tie
# has somewhere to break.
GROUPS = [
    ("Residencial", "Instalaciones en vivienda unifamiliar", "LOWEST_LOAD", 25),
    ("Comercial", "Comercios, oficinas y pequeña industria", "ROUND_ROBIN", 15),
    ("Industrial", "Cubiertas industriales y autoconsumo colectivo", "LOWEST_LOAD", 8),
]

ADVISORS = [
    ("Lucía Ferrer", "lucia.ferrer", "Residencial"),
    ("Marc Oliveras", "marc.oliveras", "Residencial"),
    ("Nerea Aguirre", "nerea.aguirre", "Residencial"),
    ("Diego Salcedo", "diego.salcedo", "Residencial"),
    ("Paula Iriarte", "paula.iriarte", "Comercial"),
    ("Andrés Chaparro", "andres.chaparro", "Comercial"),
    ("Silvia Roldán", "silvia.roldan", "Comercial"),
    ("Tomás Berenguer", "tomas.berenguer", "Comercial"),
    ("Iván Cadenas", "ivan.cadenas", "Industrial"),
    ("Rocío Valdés", "rocio.valdes", "Industrial"),
    ("Héctor Zabala", "hector.zabala", "Industrial"),
    ("Miriam Solís", "miriam.solis", "Industrial"),
]

# Viability runs before scoring: what these rule out never reaches a rule or an
# advisor, and travels as LeadDisqualified instead of LeadProcessedEvent.
DISQUALIFICATION_RULES = [
    {
        "name": "Presupuesto por debajo del mínimo",
        "conditions": [{"field": "budget", "operator": "LESS_THAN", "value": 1500}],
        "priority": 20,
    },
    {
        "name": "Consulta de la competencia",
        "conditions": [
            {"field": "company", "operator": "IN", "value": ["Solaria Directa", "EnerFake", "SunRival"]}
        ],
        "priority": 10,
    },
    {
        "name": "Sin ninguna forma de contacto",
        "conditions": [
            {"field": "email", "operator": "IS_EMPTY"},
            {"field": "phone", "operator": "IS_EMPTY"},
        ],
        "priority": 5,
    },
]

SCORING_RULES = [
    {
        "name": "Gran cuenta",
        "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 50000}],
        "score_delta": 45,
        "priority": 30,
    },
    {
        "name": "Cuenta media",
        "conditions": [{"field": "budget", "operator": "GREATER_THAN", "value": 12000}],
        "score_delta": 20,
        "priority": 20,
    },
    {
        "name": "Sector objetivo",
        "conditions": [
            {"field": "industry", "operator": "IN", "value": ["Industrial", "Logística", "Agroalimentario"]}
        ],
        "score_delta": 25,
        "priority": 15,
    },
    {
        "name": "Localizable por teléfono",
        "conditions": [{"field": "phone", "operator": "IS_NOT_EMPTY"}],
        "score_delta": 10,
        "priority": 10,
    },
    {
        "name": "Captado en la feria Genera",
        "conditions": [
            {"field": "custom_attributes.campana", "operator": "EQUALS", "value": "genera-2026"}
        ],
        "score_delta": 15,
        "priority": 5,
    },
]

# Bands are inclusive on both ends and never overlap, so the band a lead falls
# in is readable from its score alone when the demo has to explain a routing.
ASSIGNMENT_BANDS = [
    ("Cuentas industriales", 70, None, "Industrial", "LOWEST_LOAD", 30),
    ("Cuentas comerciales", 35, 69, "Comercial", "ROUND_ROBIN", 20),
    ("Residencial", 0, 34, "Residencial", "LOWEST_LOAD", 10),
]


def step(message):
    print(f"  · {message}")


def section(title):
    print(f"\n\033[1m{title}\033[0m")


def platform_admin_login(api):
    """The very first agent is created unauthenticated; after that the same
    call is refused, and logging in is the only way in."""
    email, password = PLATFORM_ADMIN
    api.post("/agents", {"name": "Root", "email": email, "password": password, "role": "ADMIN"})
    if not api.login(email, password):
        die(f"no hay forma de entrar como admin de plataforma ({email})")


def ensure_tenant(api):
    platform_admin_login(api)
    status, page = api.get("/tenants?limit=1000")
    if status != 200:
        die(f"no se pueden listar las organizaciones: {page}")
    for tenant in page.get("items", []):
        if tenant["name"] == COMPANY:
            step(f"organización «{COMPANY}» ya existía")
            return tenant["id"]
    status, tenant = api.post(
        "/tenants",
        {
            "name": COMPANY,
            "manager": {"name": "Elena Márquez", "email": MANAGER_EMAIL, "password": PASSWORD},
        },
    )
    if status != 201:
        die(f"no se pudo crear la organización: {tenant}")
    step(f"organización «{COMPANY}» creada")
    return tenant["id"]


def ensure_groups(api):
    status, page = api.get("/groups?limit=1000")
    existing = {g["name"]: g["id"] for g in page.get("items", [])} if status == 200 else {}
    ids = {}
    for name, description, strategy, capacity in GROUPS:
        if name in existing:
            ids[name] = existing[name]
            continue
        status, group = api.post(
            "/groups",
            {
                "name": name,
                "description": description,
                "default_strategy": strategy,
                "capacity_per_agent": capacity,
            },
        )
        if status != 201:
            die(f"no se pudo crear el equipo {name}: {group}")
        ids[name] = group["id"]
    step(f"{len(ids)} equipos comerciales")
    return ids


def ensure_advisors(api, group_ids):
    status, page = api.get("/agents?limit=1000")
    existing = {a["email"] for a in page.get("items", [])} if status == 200 else set()
    created = 0
    for name, handle, group in ADVISORS:
        email = f"{handle}@{DOMAIN}"
        if email in existing:
            continue
        status, agent = api.post(
            "/agents",
            {
                "name": name,
                "email": email,
                "password": PASSWORD,
                "role": "AGENT",
                "group_id": group_ids[group],
            },
        )
        if status != 201:
            die(f"no se pudo crear al asesor {email}: {agent}")
        created += 1
    step(f"{len(ADVISORS)} asesores ({created} nuevos)")


def ensure_rules(api, group_ids):
    status, page = api.get("/rules/disqualification?limit=1000")
    existing = {r["name"] for r in page.get("items", [])} if status == 200 else set()
    for rule in DISQUALIFICATION_RULES:
        if rule["name"] in existing:
            continue
        status, created = api.post("/rules/disqualification", rule)
        if status != 201:
            die(f"regla de descarte «{rule['name']}»: {created}")
    step(f"{len(DISQUALIFICATION_RULES)} reglas de descarte")

    status, page = api.get("/rules/scoring?limit=1000")
    existing = {r["name"] for r in page.get("items", [])} if status == 200 else set()
    for rule in SCORING_RULES:
        if rule["name"] in existing:
            continue
        status, created = api.post("/rules/scoring", rule)
        if status != 201:
            die(f"regla de puntuación «{rule['name']}»: {created}")
    step(f"{len(SCORING_RULES)} reglas de puntuación")

    status, page = api.get("/rules/assignment?limit=1000")
    existing = {r["name"] for r in page.get("items", [])} if status == 200 else set()
    for name, minimum, maximum, group, strategy, priority in ASSIGNMENT_BANDS:
        if name in existing:
            continue
        status, created = api.post(
            "/rules/assignment",
            {
                "name": name,
                "min_score": minimum,
                "max_score": maximum,
                "target_group_id": group_ids[group],
                "strategy": strategy,
                "priority": priority,
            },
        )
        if status != 201:
            die(f"regla de asignación «{name}»: {created}")
    step(f"{len(ASSIGNMENT_BANDS)} bandas de asignación")


def issue_credential(api, tenant_id, destination):
    """Upsert: re-running rotates the secret rather than failing, so the file
    this writes is always the one that works."""
    status, credential = api.post("/agents/integration-credential")
    if status != 201:
        print(
            f"  \033[33m!\033[0m no se pudo emitir la credencial de integración ({status}): "
            f"{credential}\n    Kafka tiene que estar levantado para esto.",
            file=sys.stderr,
        )
        return None
    destination.write_text(json.dumps(credential, indent=2) + "\n")
    step(f"credencial de integración emitida → {destination}")
    return credential


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:8001/api/v1")
    args = parser.parse_args()

    admin, api = Api(args.api), Api(args.api)

    section(f"{COMPANY} · sembrando sobre {args.api}")
    try:
        tenant_id = ensure_tenant(admin)
        if not api.login(MANAGER_EMAIL, PASSWORD):
            die(f"la organización existe pero no se puede entrar como {MANAGER_EMAIL}")
        group_ids = ensure_groups(api)
        ensure_advisors(api, group_ids)
        ensure_rules(api, group_ids)
        credential = issue_credential(api, tenant_id, Path(__file__).parent / "credenciales.local.json")
    finally:
        admin.logout()
        api.logout()

    section("Listo")
    print(f"  organización   {tenant_id}")
    print(f"  gestora        {MANAGER_EMAIL} / {PASSWORD}")
    print(f"  asesores       {ADVISORS[0][1]}@{DOMAIN} … / {PASSWORD}")
    if credential:
        print(f"  topic Kafka    {credential['kafka_topic']}")
        print(f"  usuario Kafka  {credential['kafka_username']}")
    print("\n  Carga masiva:  demo/leads-lote-1.csv · demo/leads-lote-2.xlsx · demo/leads-sucios.csv")


if __name__ == "__main__":
    main()

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from domain.entities.auth_session import AuthSession
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.main import app


def session_headers(agent) -> dict[str, str]:
    """Persist a browser-equivalent opaque session for API tests that seed agents directly."""
    token = secrets.token_urlsafe(32)
    with PostgresUnitOfWork(app.state.container.database) as uow:
        uow.sessions.save(AuthSession(
            token_hash=sha256(token.encode()).hexdigest(), agent_id=agent.id.value,
            created_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        ))
    return {"Cookie": f"leads_session={token}"}

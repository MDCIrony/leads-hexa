import uuid
from hashlib import sha256

import pyotp
from gateway_client import GatewayClient

from domain.entities.agent import Agent
from domain.value_objects.enums import AgentRole
from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
from infrastructure.adapters.output.security.bcrypt_password_hasher import BcryptPasswordHasher
from infrastructure.main import app

_PASSWORD = "Secret123"
_HASHED = BcryptPasswordHasher().hash(_PASSWORD)


def _agent(client):
    agent = Agent.create(
        "MFA HTTP", f"mfa_http_{uuid.uuid4().hex[:8]}@test.com", role=AgentRole.MANAGER,
        hashed_password=_HASHED, tenant_id=uuid.uuid4(),
    )
    with PostgresUnitOfWork(client.app.state.container.database) as uow:
        uow.agents.save(agent)
    return agent


def _login(client, agent):
    return client.post("/api/v1/auth/login", data={"username": agent.email, "password": _PASSWORD})


def test_mfa_enrollment_login_and_cookie_contract():
    with GatewayClient(app) as client:
        agent = _agent(client)
        initial = _login(client, agent)
        initial_session = initial.cookies["leads_session"]
        setup = client.post("/api/v1/auth/mfa/setup", json={"password": _PASSWORD})
        assert setup.status_code == 200
        secret = setup.json()["secret"]
        assert "otpauth://totp/" in setup.json()["otpauth_uri"]

        confirmation = client.post("/api/v1/auth/mfa/setup/confirm", json={"code": pyotp.TOTP(secret).now()})
        assert confirmation.status_code == 200
        recovery_codes = confirmation.json()["recovery_codes"]
        assert len(recovery_codes) == 8
        assert all(len(code) == 32 for code in recovery_codes)
        assert secret not in confirmation.text

        me = client.get("/api/v1/auth/me", headers={"Cookie": f"leads_session={initial_session}"})
        assert me.json()["mfa_enabled"] is True

        required = _login(client, agent)
        assert required.json() == {"status": "MFA_REQUIRED"}
        raw = required.headers["set-cookie"]
        assert "leads_mfa_challenge=" in raw
        assert "Path=/api/v1/auth/mfa" in raw
        assert "Max-Age=300" in raw
        assert "HttpOnly" in raw
        assert "leads_session=" in raw

        verified = client.post("/api/v1/auth/mfa/verify", json={"code": recovery_codes[0]})
        assert verified.json() == {"status": "AUTHENTICATED"}
        assert "leads_session=" in verified.headers["set-cookie"]
        assert "leads_mfa_challenge=" in verified.headers["set-cookie"]

        with client.app.state.container.database.get_connection(autocommit=True) as conn:
            row = conn.execute("SELECT secret_ciphertext FROM agent_mfa WHERE agent_id = %s", (agent.id.value,)).fetchone()
        assert row["secret_ciphertext"] != secret
        assert sha256(recovery_codes[0].encode()).hexdigest() not in verified.text


def test_mfa_factor_failure_is_generic_and_fifth_attempt_exhausts_challenge():
    with GatewayClient(app) as client:
        agent = _agent(client)
        _login(client, agent)
        secret = client.post("/api/v1/auth/mfa/setup", json={"password": _PASSWORD}).json()["secret"]
        client.post("/api/v1/auth/mfa/setup/confirm", json={"code": pyotp.TOTP(secret).now()})
        required = _login(client, agent)
        challenge = required.cookies["leads_mfa_challenge"]
        client.cookies.clear()

        responses = [
            client.post("/api/v1/auth/mfa/verify", json={"code": "wrong"}, headers={"Cookie": f"leads_mfa_challenge={challenge}"})
            for _ in range(6)
        ]

    assert {response.status_code for response in responses} == {401}
    assert {response.json()["message"] for response in responses} == {"Invalid authentication factor"}
    assert "leads_mfa_challenge=" not in responses[0].headers.get("set-cookie", "")
    assert "leads_mfa_challenge=" in responses[4].headers.get("set-cookie", "")

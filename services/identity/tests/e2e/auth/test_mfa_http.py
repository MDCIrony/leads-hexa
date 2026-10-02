from hashlib import sha256

import pyotp

from tests.e2e.seeds import PASSWORD, cookie, login, seed_agent


def _enroll(client, agent) -> tuple[str, list[str], str]:
    session = login(client, agent.email).cookies["leads_session"]
    secret = client.post("/api/v1/auth/mfa/setup", json={"password": PASSWORD}).json()["secret"]
    codes = client.post("/api/v1/auth/mfa/setup/confirm", json={"code": pyotp.TOTP(secret).now()})
    return secret, codes.json()["recovery_codes"], session


def test_mfa_enrollment_login_and_cookie_contract(client):
    agent = seed_agent(client)
    initial_session = login(client, agent.email).cookies["leads_session"]
    setup = client.post("/api/v1/auth/mfa/setup", json={"password": PASSWORD})
    assert setup.status_code == 200
    secret = setup.json()["secret"]
    assert "otpauth://totp/" in setup.json()["otpauth_uri"]

    confirmation = client.post("/api/v1/auth/mfa/setup/confirm", json={"code": pyotp.TOTP(secret).now()})
    assert confirmation.status_code == 200
    recovery_codes = confirmation.json()["recovery_codes"]
    assert len(recovery_codes) == 8
    assert all(len(code) == 32 for code in recovery_codes)
    assert secret not in confirmation.text

    assert client.get("/api/v1/auth/me", headers=cookie(initial_session)).json()["mfa_enabled"] is True

    required = login(client, agent.email)
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


def test_mfa_factor_failure_is_generic_and_fifth_attempt_exhausts_challenge(client):
    agent = seed_agent(client)
    _enroll(client, agent)
    challenge = login(client, agent.email).cookies["leads_mfa_challenge"]
    client.cookies.clear()

    responses = [
        client.post("/api/v1/auth/mfa/verify", json={"code": "wrong"}, headers={"Cookie": f"leads_mfa_challenge={challenge}"})
        for _ in range(6)
    ]

    assert {response.status_code for response in responses} == {401}
    assert {response.json()["error_code"] for response in responses} == {"INVALID_CREDENTIALS"}
    assert {response.json()["message"] for response in responses} == {"Invalid authentication factor"}
    assert "leads_mfa_challenge=" not in responses[0].headers.get("set-cookie", "")
    assert "leads_mfa_challenge=" in responses[4].headers.get("set-cookie", "")


def test_regenerating_codes_and_disabling_need_password_and_a_live_factor(client):
    agent = seed_agent(client)
    secret, codes, session = _enroll(client, agent)
    headers = cookie(session)
    client.cookies.clear()

    wrong_password = client.post(
        "/api/v1/auth/mfa/recovery-codes/regenerate", json={"password": "nope", "code": codes[0]}, headers=headers,
    )
    regenerated = client.post(
        "/api/v1/auth/mfa/recovery-codes/regenerate", json={"password": PASSWORD, "code": codes[0]}, headers=headers,
    )
    disabled = client.post(
        "/api/v1/auth/mfa/disable", json={"password": PASSWORD, "code": regenerated.json()["recovery_codes"][0]},
        headers=headers,
    )

    assert (wrong_password.status_code, wrong_password.json()["error_code"]) == (401, "INVALID_CREDENTIALS")
    assert regenerated.status_code == 200
    assert len(regenerated.json()["recovery_codes"]) == 8
    assert disabled.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).json()["mfa_enabled"] is False


def test_mfa_routes_need_a_session(client):
    responses = [
        client.post("/api/v1/auth/mfa/setup", json={"password": PASSWORD}),
        client.post("/api/v1/auth/mfa/setup/confirm", json={"code": "123456"}),
        client.post("/api/v1/auth/mfa/disable", json={"password": PASSWORD, "code": "123456"}),
    ]

    assert {response.status_code for response in responses} == {401}
    assert {response.json()["error_code"] for response in responses} == {"UNAUTHORIZED"}

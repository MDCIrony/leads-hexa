from chassis.testing.contracts import assert_conforms, load_fixture

from tests import environment

_URL = "/internal/v1/service-tokens"


def _request(**overrides) -> dict:
    return {
        "client_id": environment.SERVICE_CLIENT_ID, "client_secret": environment.SERVICE_CLIENT_SECRET,
        "audience": "identity", **overrides,
    }


def test_a_known_client_gets_a_token_for_an_allowed_audience(direct):
    response = direct.post(_URL, json=_request())

    assert response.status_code == 200
    body = response.json()
    assert_conforms(body, "schemas/identity/service-token.v1.schema.json")
    assert set(body) == set(load_fixture("identity/service-token.v1.json"))
    assert body["expires_in"] == 300
    claims = direct.app.state.container.service_token_verifier.verify(body["access_token"], {"lead-core"})
    assert (claims.sub, claims.aud) == ("lead-core", "identity")


def test_bad_credentials_and_foreign_audiences_answer_the_same_401(direct):
    responses = [
        direct.post(_URL, json=_request(client_secret="wrong")),
        direct.post(_URL, json=_request(client_id="intake")),
        direct.post(_URL, json=_request(audience="lead-core")),
    ]

    assert {r.status_code for r in responses} == {401}
    assert {r.json()["error_code"] for r in responses} == {"UNAUTHORIZED"}
    assert len({r.json()["message"] for r in responses}) == 1
    assert all(set(r.json()) == {"error", "error_code", "message"} for r in responses)
    assert all(environment.SERVICE_CLIENT_SECRET not in r.text for r in responses)


def test_an_incomplete_request_is_a_validation_error(direct):
    response = direct.post(_URL, json={"client_id": environment.SERVICE_CLIENT_ID})

    assert response.status_code == 422
    assert response.json()["error_code"] == "VALIDATION_ERROR"

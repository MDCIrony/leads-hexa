import uuid

from fastapi.testclient import TestClient

from tests.e2e.helpers.gateway_client import tenant_of
from tests.tokens import mint_service_token


def admit_lead(client, headers: dict, payload: dict) -> dict:
    """Admits one lead the way intake does and returns the admission result.

    The gateway never exposes /internal/, so this skips GatewayClient's filter
    and calls the app with a service token, as intake would."""
    candidate = {"phone": None, "email": None, "custom_attributes": {}, **payload}
    candidate["budget"] = str(candidate["budget"])
    response = TestClient.request(
        client, "POST", "/internal/v1/admissions",
        json={"tenant_id": tenant_of(headers), "intake_record_id": str(uuid.uuid4()),
              "source_id": str(uuid.uuid4()), "candidate": candidate},
        headers={"Authorization": f"Bearer {mint_service_token()}"},
    )
    assert response.status_code == 200, response.text
    return response.json()

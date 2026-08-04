import os
import pytest

os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-production"

from infrastructure.security.jwt_service import create_access_token, decode_access_token


def test_create_and_decode_round_trip():
    token = create_access_token(agent_id="11111111-1111-1111-1111-111111111111", role="ADMIN", tenant_id=None)
    payload = decode_access_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["role"] == "ADMIN"
    assert payload["tenant_id"] is None


def test_decode_preserves_tenant_id_when_present():
    token = create_access_token(agent_id="agent-1", role="MANAGER", tenant_id="tenant-1")
    payload = decode_access_token(token)
    assert payload["tenant_id"] == "tenant-1"


def test_decode_rejects_a_tampered_token():
    token = create_access_token(agent_id="agent-1", role="AGENT", tenant_id=None)
    tampered = token[:-2] + "xx"
    with pytest.raises(Exception):
        decode_access_token(tampered)

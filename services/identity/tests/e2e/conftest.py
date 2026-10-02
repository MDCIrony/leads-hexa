import pytest
from fastapi.testclient import TestClient

from infrastructure.main import app
from tests.e2e.gateway_client import GatewayClient


@pytest.fixture
def client(test_db):
    """Through the gateway: entering it runs the lifespan, which builds the container."""
    with GatewayClient(app) as gateway:
        yield gateway


@pytest.fixture
def direct(test_db):
    """Straight to the service, as the gateway itself or another service calls it."""
    with TestClient(app) as service:
        yield service

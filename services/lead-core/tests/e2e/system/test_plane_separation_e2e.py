"""The platform plane reaches no organization data, and within an organization
the pipeline is the manager's. Who is who comes from identity; what each one
reaches here is lead-core's to enforce."""
from tests.e2e.helpers.auth_helpers import admin_headers, agent_of, seed_org_manager
from tests.e2e.helpers.gateway_client import GatewayClient
from infrastructure.main import app


def test_platform_admin_reaches_no_organization_data():
    with GatewayClient(app) as client:
        admin = admin_headers()

        # The whole point of the phase: the platform plane reaches no data.
        assert client.get("/api/v1/leads", headers=admin).status_code == 403
        assert client.get("/api/v1/advisors", headers=admin).status_code == 403
        assert client.get("/api/v1/rules/scoring", headers=admin).status_code == 403


def test_manager_works_inside_its_organization():
    with GatewayClient(app) as client:
        ana = seed_org_manager("Ana")

        assert client.get("/api/v1/leads", headers=ana).status_code == 200


def test_sales_agent_cannot_read_the_whole_organization_pipeline():
    """GET /leads is the manager's view of every lead in the organization.

    Belonging to the organization is not enough to read it: a sales agent
    would see its colleagues' leads. Its own view is GET /leads/mine.
    Asserted here so nobody relaxes the guard back to plain authentication,
    which is exactly how the platform Admin once slipped in."""
    with GatewayClient(app) as client:
        ana = seed_org_manager("Ana")
        sales, _ = agent_of(ana, "Sales Person")

        assert client.get("/api/v1/leads", headers=sales).status_code == 403
        assert client.get("/api/v1/leads", headers=ana).status_code == 200

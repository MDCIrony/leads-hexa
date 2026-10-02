import uuid

from gateway_client import GatewayClient
from infrastructure.main import app

from test_intake_authentication import _agent_auth_headers
from test_lead_endpoints import _manager_auth_headers, _seed_tenant_with_sources
from _intake_helpers import ingest_and_resolve

_VALID_PAYLOAD = {
    "first_name": "Ana",
    "last_name": "Diaz",
    "company": "Acme",
    "budget": 9000.0,
    "industry": "Tech",
}


def test_rejected_payload_can_be_corrected_and_promoted_through_the_inbox():
    """Acceptance criterion 2, end to end: an unreadable payload lands in the
    inbox with its failure detail, the manager corrects and promotes it, the
    retry reuses the same row, and a second promotion attempt is refused."""
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        # 1. V1 retired the schema's email check entirely, so this reaches the
        # domain unfiltered — the EmailAddress regex rejects the double "@"
        # and the record lands REJECTED in the tray instead of being lost.
        bad_payload = {**_VALID_PAYLOAD, "email": "jane@@example.com"}
        record_id = ingest_and_resolve(client, headers, bad_payload)["id"]
        assert record_id

        # 2. Shows up in the inbox with its field error and original payload.
        listing = client.get("/api/v1/intake/records?status=REJECTED", headers=headers)
        assert listing.status_code == 200
        listed = next(item for item in listing.json()["items"] if item["id"] == record_id)
        assert listed["payload"]["email"] == "jane@@example.com"
        assert any(error["field"] == "email" for error in listed["errors"])

        # 3. Promote with the corrected payload.
        fixed_payload = {**_VALID_PAYLOAD, "email": "ana@example.com"}
        promote_resp = client.post(
            f"/api/v1/intake/records/{record_id}/promote",
            json={"payload": fixed_payload},
            headers=headers,
        )
        assert promote_resp.status_code == 200
        promoted = promote_resp.json()
        assert promoted["intake_record_id"] == record_id
        assert promoted["lead_id"]

        # 4. The record is PROMOTED with its lead_id, and the lead exists.
        lead_resp = client.get(f"/api/v1/leads/{promoted['lead_id']}", headers=headers)
        assert lead_resp.status_code == 200

        # 5. Still one row for this payload, not two: the retry reused it.
        all_records = client.get("/api/v1/intake/records", headers=headers).json()
        assert all_records["total"] == 1

        # 6. Promoting the same record again fails, and no second lead appears.
        retry_resp = client.post(
            f"/api/v1/intake/records/{record_id}/promote",
            json={"payload": fixed_payload},
            headers=headers,
        )
        assert retry_resp.status_code == 400
        assert retry_resp.json()["error_code"] == "INVALID_INTAKE_TRANSITION"

        leads_after_retry = client.get("/api/v1/leads", headers=headers).json()
        assert leads_after_retry["total"] == 1


def test_promote_with_a_still_invalid_payload_stays_rejected_with_new_errors():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        bad_payload = {**_VALID_PAYLOAD, "email": "jane@@example.com"}
        record_id = ingest_and_resolve(client, headers, bad_payload)["id"]

        still_bad_payload = {**_VALID_PAYLOAD, "email": "ana@example.com", "budget": -50.0}
        promote_resp = client.post(
            f"/api/v1/intake/records/{record_id}/promote",
            json={"payload": still_bad_payload},
            headers=headers,
        )
        assert promote_resp.status_code == 400
        assert promote_resp.json()["error_code"] == "INVALID_BUDGET"

        listing = client.get("/api/v1/intake/records?status=REJECTED", headers=headers).json()
        record = next(item for item in listing["items"] if item["id"] == record_id)
        assert record["errors"][0]["field"] == "budget"


def test_discard_a_rejected_record():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        bad_payload = {**_VALID_PAYLOAD, "email": "jane@@example.com"}
        record_id = ingest_and_resolve(client, headers, bad_payload)["id"]

        discard_resp = client.post(f"/api/v1/intake/records/{record_id}/discard", headers=headers)
        assert discard_resp.status_code == 204

        listing = client.get("/api/v1/intake/records?status=DISCARDED", headers=headers).json()
        assert any(item["id"] == record_id for item in listing["items"])


def test_discard_an_already_promoted_record_fails():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        record_id = ingest_and_resolve(client, headers, _VALID_PAYLOAD)["id"]

        discard_resp = client.post(f"/api/v1/intake/records/{record_id}/discard", headers=headers)
        assert discard_resp.status_code == 400
        assert discard_resp.json()["error_code"] == "INVALID_INTAKE_TRANSITION"


def test_mixed_batch_upload_leaves_one_promoted_and_one_rejected_in_the_inbox():
    tenant_id = str(uuid.uuid4())
    csv_content = (
        "first_name,last_name,email,company,budget,industry\n"
        "Ana,Silva,ana@company.com,CompanyA,20000,Finance\n"
        "Mal,Formado,email-sin-arroba,CompanyB,10000,Retail\n"
    ).encode("utf-8")
    files = {"file": ("leads.csv", csv_content, "text/csv")}

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 202
        data = response.json()
        assert data["record_ids"] == []

        records = client.get(f"/api/v1/intake/records?job_id={data['job_id']}", headers=headers).json()
        items = records["items"]
        assert len(items) == 2
        by_status = {item["status"]: item for item in items}
        assert set(by_status) == {"PROMOTED", "REJECTED"}
        assert by_status["PROMOTED"]["lead_id"]
        assert by_status["REJECTED"]["errors"]


def test_batch_upload_with_an_unreadable_file_fails_the_job_without_a_500():
    tenant_id = str(uuid.uuid4())
    files = {"file": ("leads.xlsx", b"not a real spreadsheet", "application/octet-stream")}

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        records = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=headers).json()
        assert records["items"] == []

        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        from domain.value_objects.enums import IntakeJobStatus
        uow = PostgresUnitOfWork(app.state.container.database)
        with uow:
            job = uow.intake_jobs.get_by_id_and_tenant(uuid.UUID(job_id), uuid.UUID(tenant_id))
        assert job.status == IntakeJobStatus.FAILED


def test_batch_upload_with_only_a_header_completes_with_zero_items():
    tenant_id = str(uuid.uuid4())
    csv_content = "first_name,last_name,email,company,budget,industry\n".encode("utf-8")
    files = {"file": ("leads.csv", csv_content, "text/csv")}

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.post("/api/v1/intake/leads/batch-upload", files=files, headers=headers)
        assert response.status_code == 202
        job_id = response.json()["job_id"]

        records = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=headers).json()
        assert records["items"] == []

        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork
        from domain.value_objects.enums import IntakeJobStatus
        uow = PostgresUnitOfWork(app.state.container.database)
        with uow:
            job = uow.intake_jobs.get_by_id_and_tenant(uuid.UUID(job_id), uuid.UUID(tenant_id))
        assert job.status == IntakeJobStatus.COMPLETED
        assert job.total_items == 0


def test_cross_organization_access_to_intake_records_is_rejected():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_a)
        _seed_tenant_with_sources(tenant_b)
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        record_id = ingest_and_resolve(client, headers_a, _VALID_PAYLOAD)["id"]

        # Never leaks into another organization's own listing.
        listing_b = client.get("/api/v1/intake/records", headers=headers_b).json()
        assert all(item["id"] != record_id for item in listing_b["items"])

        promote_resp = client.post(
            f"/api/v1/intake/records/{record_id}/promote",
            json={"payload": _VALID_PAYLOAD},
            headers=headers_b,
        )
        assert promote_resp.status_code == 404
        assert promote_resp.json()["error_code"] == "INTAKE_RECORD_NOT_FOUND"

        discard_resp = client.post(f"/api/v1/intake/records/{record_id}/discard", headers=headers_b)
        assert discard_resp.status_code == 404
        assert discard_resp.json()["error_code"] == "INTAKE_RECORD_NOT_FOUND"


def test_agent_role_is_forbidden_from_all_three_inbox_endpoints():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        manager_headers = _manager_auth_headers(tenant_id)
        agent_headers = _agent_auth_headers(tenant_id)

        record_id = ingest_and_resolve(client, manager_headers, _VALID_PAYLOAD)["id"]

        assert client.get("/api/v1/intake/records", headers=agent_headers).status_code == 403
        assert client.post(
            f"/api/v1/intake/records/{record_id}/promote",
            json={"payload": _VALID_PAYLOAD},
            headers=agent_headers,
        ).status_code == 403
        assert client.post(
            f"/api/v1/intake/records/{record_id}/discard", headers=agent_headers
        ).status_code == 403


def test_a_file_over_10_mb_is_refused_by_the_endpoint_itself():
    """Straight to the app, no gateway: the backend must not rely on nginx
    for the limit, nor read the whole body before refusing it."""
    from fastapi.testclient import TestClient
    from domain.entities.agent import Agent
    from domain.value_objects.enums import AgentRole
    from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork

    tenant_id = str(uuid.uuid4())
    files = {"file": ("big.csv", b"x" * (10 * 1024 * 1024 + 1), "text/csv")}

    with TestClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        manager = Agent.create(
            name="Manager", email=f"m_{uuid.uuid4().hex[:6]}@test.com", role=AgentRole.MANAGER, tenant_id=tenant_id,
        )
        with PostgresUnitOfWork(app.state.container.database) as uow:
            uow.agents.save(manager)
        bearer = app.state.container.token_issuer.issue(manager, "human")

        response = client.post(
            "/api/v1/intake/leads/batch-upload", files=files, headers={"Authorization": f"Bearer {bearer}"},
        )
        jobs = client.get("/api/v1/intake/jobs", headers={"Authorization": f"Bearer {bearer}"}).json()

    assert response.status_code == 413
    assert response.json() == {"error": True, "error_code": "PAYLOAD_TOO_LARGE", "message": "Request body too large"}
    assert jobs["total"] == 0

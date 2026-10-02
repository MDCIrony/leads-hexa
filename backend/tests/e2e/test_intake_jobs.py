import uuid

from gateway_client import GatewayClient
from infrastructure.main import app

from _intake_helpers import ingest_and_resolve
from test_intake_authentication import _agent_auth_headers
from test_lead_endpoints import _manager_auth_headers, _seed_tenant_with_sources

_VALID_PAYLOAD = {
    "first_name": "Ana",
    "last_name": "Diaz",
    "company": "Acme",
    "budget": 9000.0,
    "industry": "Tech",
}


def test_ingest_a_lead_and_query_its_job():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        accepted = client.post("/api/v1/intake/leads/ingest", json=_VALID_PAYLOAD, headers=headers)
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]

        job = client.get(f"/api/v1/intake/jobs/{job_id}", headers=headers)
        assert job.status_code == 200
        data = job.json()
        assert data["status"] == "COMPLETED"
        assert data["total_items"] == 1
        assert data["succeeded"] == 1
        assert data["failed"] == 0


def test_list_jobs_filtered_by_status():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        ingest_and_resolve(client, headers, _VALID_PAYLOAD)  # ends up COMPLETED

        unreadable = {"file": ("leads.xlsx", b"not a real spreadsheet", "application/octet-stream")}
        client.post("/api/v1/intake/leads/batch-upload", files=unreadable, headers=headers)  # ends up FAILED

        completed = client.get("/api/v1/intake/jobs?status=COMPLETED", headers=headers)
        assert completed.status_code == 200
        completed_data = completed.json()
        assert completed_data["total"] == 1
        assert all(item["status"] == "COMPLETED" for item in completed_data["items"])

        failed = client.get("/api/v1/intake/jobs?status=FAILED", headers=headers).json()
        assert failed["total"] == 1
        assert failed["items"][0]["status"] == "FAILED"


def test_list_jobs_with_unknown_status_is_a_domain_error_not_a_500():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        response = client.get("/api/v1/intake/jobs?status=NOT_A_STATUS", headers=headers)
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_JOB_STATUS"


def test_get_job_from_another_organization_is_404():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_a)
        _seed_tenant_with_sources(tenant_b)
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        accepted = client.post("/api/v1/intake/leads/ingest", json=_VALID_PAYLOAD, headers=headers_a)
        job_id = accepted.json()["job_id"]

        response = client.get(f"/api/v1/intake/jobs/{job_id}", headers=headers_b)
        assert response.status_code == 404
        assert response.json()["error_code"] == "INTAKE_JOB_NOT_FOUND"


def test_reprocess_job_from_another_organization_is_404():
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_a)
        _seed_tenant_with_sources(tenant_b)
        headers_a = _manager_auth_headers(tenant_a)
        headers_b = _manager_auth_headers(tenant_b)

        accepted = client.post("/api/v1/intake/leads/ingest", json=_VALID_PAYLOAD, headers=headers_a)
        job_id = accepted.json()["job_id"]

        response = client.post(f"/api/v1/intake/jobs/{job_id}/reprocess", headers=headers_b)
        assert response.status_code == 404
        assert response.json()["error_code"] == "INTAKE_JOB_NOT_FOUND"


def test_reprocess_an_already_completed_job_is_refused():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        accepted = client.post("/api/v1/intake/leads/ingest", json=_VALID_PAYLOAD, headers=headers)
        job_id = accepted.json()["job_id"]  # already COMPLETED by the time control returns

        response = client.post(f"/api/v1/intake/jobs/{job_id}/reprocess", headers=headers)
        assert response.status_code == 400
        assert response.json()["error_code"] == "INVALID_JOB_TRANSITION"


def test_agent_role_is_forbidden_from_all_three_job_endpoints():
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        manager_headers = _manager_auth_headers(tenant_id)
        agent_headers = _agent_auth_headers(tenant_id)

        accepted = client.post("/api/v1/intake/leads/ingest", json=_VALID_PAYLOAD, headers=manager_headers)
        job_id = accepted.json()["job_id"]

        assert client.get("/api/v1/intake/jobs", headers=agent_headers).status_code == 403
        assert client.get(f"/api/v1/intake/jobs/{job_id}", headers=agent_headers).status_code == 403
        assert client.post(
            f"/api/v1/intake/jobs/{job_id}/reprocess", headers=agent_headers
        ).status_code == 403


def test_reprocessing_a_stalled_job_resolves_its_pending_records_without_duplicating_leads():
    """Acceptance criterion 4: a job interrupted before phase 2 ever ran stays
    visible with its PENDING records, and reprocess finishes it. Reprocessing
    it again afterwards must not create a second lead nor double the
    counters — guaranteed here because a COMPLETED job refuses reprocessing
    outright, before touching a single record. There is no HTTP path that
    leaves a job in this half-done state, so it is fabricated directly
    through the repositories, exactly as an interrupted background run would
    leave it.
    """
    tenant_id = str(uuid.uuid4())

    with GatewayClient(app) as client:
        _seed_tenant_with_sources(tenant_id)
        headers = _manager_auth_headers(tenant_id)

        from domain.entities.intake_job import IntakeJob
        from domain.entities.intake_record import IntakeRecord
        from domain.value_objects.enums import IntakeJobKind, LeadSourceKind
        from infrastructure.adapters.output.persistence.postgres_unit_of_work import PostgresUnitOfWork

        db = app.state.container.database
        uow = PostgresUnitOfWork(db)
        with uow:
            source = uow.sources.get_by_kind(uuid.UUID(tenant_id), LeadSourceKind.MANUAL_FORM)
        source_id = str(source.id)

        job = IntakeJob.create(tenant_id=tenant_id, source_id=source_id, kind=IntakeJobKind.BATCH, total_items=2)
        good_record = IntakeRecord.create(
            tenant_id=tenant_id, source_id=source_id, payload=_VALID_PAYLOAD, job_id=job.id,
        )
        bad_record = IntakeRecord.create(
            tenant_id=tenant_id,
            source_id=source_id,
            payload={**_VALID_PAYLOAD, "email": "jane@@example.com"},
            job_id=job.id,
        )
        with uow:
            uow.intake_jobs.save(job)
            uow.intake_records.save(good_record)
            uow.intake_records.save(bad_record)

        job_id = str(job.id)

        first = client.post(f"/api/v1/intake/jobs/{job_id}/reprocess", headers=headers)
        assert first.status_code == 202, first.text
        # Queued, not run in the request: the job comes back as it stands.
        assert first.json()["status"] == "PENDING"
        data = client.get(f"/api/v1/intake/jobs/{job_id}", headers=headers).json()
        assert data["status"] == "COMPLETED"
        assert data["total_items"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1

        records = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=headers).json()["items"]
        assert {item["status"] for item in records} == {"PROMOTED", "REJECTED"}

        leads_after_first = client.get("/api/v1/leads", headers=headers).json()["total"]
        assert leads_after_first == 1

        second = client.post(f"/api/v1/intake/jobs/{job_id}/reprocess", headers=headers)
        assert second.status_code == 400
        assert second.json()["error_code"] == "INVALID_JOB_TRANSITION"

        leads_after_second = client.get("/api/v1/leads", headers=headers).json()["total"]
        assert leads_after_second == 1

        unchanged = client.get(f"/api/v1/intake/jobs/{job_id}", headers=headers).json()
        assert unchanged["succeeded"] == 1
        assert unchanged["failed"] == 1

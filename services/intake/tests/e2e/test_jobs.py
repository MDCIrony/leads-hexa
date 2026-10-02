from domain.jobs.intake_job import IntakeJob
from domain.records.intake_record import IntakeRecord
from domain.value_objects.enums import IntakeJobKind, LeadSourceKind
from tests.e2e.helpers import BAD_EMAIL_PAYLOAD, VALID_PAYLOAD, ingest_and_resolve

JOBS = "/api/v1/intake/jobs"


def test_ingest_a_lead_and_query_its_job(client, organization):
    manager = organization().manager
    job_id = client.post("/api/v1/intake/leads/ingest", json=VALID_PAYLOAD, headers=manager).json()["job_id"]

    job = client.get(f"{JOBS}/{job_id}", headers=manager)

    assert job.status_code == 200
    data = job.json()
    assert (data["status"], data["total_items"], data["succeeded"], data["failed"]) == ("COMPLETED", 1, 1, 0)
    assert set(data) == {
        "id", "source_id", "kind", "status", "total_items", "succeeded", "failed", "created_at", "completed_at",
    }


def test_list_jobs_filtered_by_status(client, organization):
    manager = organization().manager
    ingest_and_resolve(client, manager, VALID_PAYLOAD)
    unreadable = {"file": ("leads.xlsx", b"not a real spreadsheet", "application/octet-stream")}
    client.post("/api/v1/intake/leads/batch-upload", files=unreadable, headers=manager)

    completed = client.get(f"{JOBS}?status=COMPLETED", headers=manager).json()
    failed = client.get(f"{JOBS}?status=FAILED", headers=manager).json()

    assert (completed["total"], completed["items"][0]["status"]) == (1, "COMPLETED")
    assert (failed["total"], failed["items"][0]["status"]) == (1, "FAILED")


def test_list_jobs_with_an_unknown_status_is_a_domain_error_not_a_500(client, organization):
    response = client.get(f"{JOBS}?status=NOT_A_STATUS", headers=organization().manager)

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_JOB_STATUS"


def test_reprocess_an_already_completed_job_is_refused(client, organization):
    manager = organization().manager
    job_id = client.post("/api/v1/intake/leads/ingest", json=VALID_PAYLOAD, headers=manager).json()["job_id"]

    response = client.post(f"{JOBS}/{job_id}/reprocess", headers=manager)

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_JOB_TRANSITION"


def test_reprocessing_a_stalled_job_resolves_its_pending_records_without_duplicating_leads(
    client, organization, container, lead_core,
):
    """No HTTP path leaves a job half done, so it is fabricated through the
    repositories, exactly as a run that died mid-batch would leave it."""
    org = organization()
    with container.unit_of_work() as uow:
        source_id = uow.sources.get_by_kind(org.tenant_id, LeadSourceKind.MANUAL_FORM).id.value
        job = uow.intake_jobs.save(
            IntakeJob.create(tenant_id=org.tenant_id, source_id=source_id, kind=IntakeJobKind.BATCH, total_items=2)
        )
        for payload in (VALID_PAYLOAD, BAD_EMAIL_PAYLOAD):
            uow.intake_records.save(IntakeRecord.create(
                tenant_id=org.tenant_id, source_id=source_id, job_id=job.id.value, payload=payload,
            ))
    job_id = str(job.id)

    first = client.post(f"{JOBS}/{job_id}/reprocess", headers=org.manager)

    assert first.status_code == 202, first.text
    # Queued, not run in the request: the job comes back as it stood.
    assert first.json()["status"] == "PENDING"
    data = client.get(f"{JOBS}/{job_id}", headers=org.manager).json()
    assert (data["status"], data["total_items"], data["succeeded"], data["failed"]) == ("COMPLETED", 2, 1, 1)
    records = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=org.manager).json()["items"]
    assert {item["status"] for item in records} == {"PROMOTED", "REJECTED"}
    assert len(lead_core.leads) == 1

    second = client.post(f"{JOBS}/{job_id}/reprocess", headers=org.manager)

    assert (second.status_code, second.json()["error_code"]) == (400, "INVALID_JOB_TRANSITION")
    assert len(lead_core.leads) == 1


def test_a_job_interrupted_by_lead_core_stays_open_and_a_reprocess_finishes_it(client, organization, lead_core):
    manager = organization().manager
    lead_core.down = True
    job_id = client.post("/api/v1/intake/leads/ingest", json=VALID_PAYLOAD, headers=manager).json()["job_id"]

    stalled = client.get(f"{JOBS}/{job_id}", headers=manager).json()

    assert stalled["status"] == "PROCESSING"
    lead_core.down = False
    assert client.post(f"{JOBS}/{job_id}/reprocess", headers=manager).status_code == 202
    assert client.get(f"{JOBS}/{job_id}", headers=manager).json()["status"] == "COMPLETED"


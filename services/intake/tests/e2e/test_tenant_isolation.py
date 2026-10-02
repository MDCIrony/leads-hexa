from tests.e2e.helpers import VALID_PAYLOAD, ingest_and_resolve


def test_ingest_without_a_credential_is_401(client, organization):
    organization()

    assert client.post("/api/v1/intake/leads/ingest", json=VALID_PAYLOAD).status_code == 401


def test_a_client_supplied_bearer_never_reaches_the_service(client, organization):
    org = organization()
    forged = {"Authorization": org.direct["Authorization"]}

    assert client.get("/api/v1/intake/records", headers=forged).status_code == 401


def test_ingest_ignores_a_tenant_id_in_the_body_and_uses_the_token(client, organization):
    a, b = organization(), organization()

    record = ingest_and_resolve(client, a.manager, {**VALID_PAYLOAD, "tenant_id": str(b.tenant_id)})

    assert record["status"] == "PROMOTED"
    assert client.get("/api/v1/intake/records", headers=a.manager).json()["total"] == 1
    assert client.get("/api/v1/intake/records", headers=b.manager).json()["total"] == 0


def test_a_record_of_another_organization_is_404_for_promote_and_discard(client, organization):
    a, b = organization(), organization()
    record_id = ingest_and_resolve(client, a.manager, VALID_PAYLOAD)["id"]

    promote = client.post(f"/api/v1/intake/records/{record_id}/promote", json={"payload": VALID_PAYLOAD}, headers=b.manager)
    discard = client.post(f"/api/v1/intake/records/{record_id}/discard", headers=b.manager)

    assert (promote.status_code, promote.json()["error_code"]) == (404, "INTAKE_RECORD_NOT_FOUND")
    assert (discard.status_code, discard.json()["error_code"]) == (404, "INTAKE_RECORD_NOT_FOUND")


def test_a_job_of_another_organization_is_404_for_get_and_reprocess(client, organization):
    a, b = organization(), organization()
    job_id = client.post("/api/v1/intake/leads/ingest", json=VALID_PAYLOAD, headers=a.manager).json()["job_id"]

    read = client.get(f"/api/v1/intake/jobs/{job_id}", headers=b.manager)
    reprocess = client.post(f"/api/v1/intake/jobs/{job_id}/reprocess", headers=b.manager)

    assert (read.status_code, read.json()["error_code"]) == (404, "INTAKE_JOB_NOT_FOUND")
    assert (reprocess.status_code, reprocess.json()["error_code"]) == (404, "INTAKE_JOB_NOT_FOUND")
    assert client.get("/api/v1/intake/jobs", headers=b.manager).json()["total"] == 0


def test_an_agent_is_forbidden_even_after_a_manager_filled_the_inbox(client, organization):
    org = organization()
    record_id = ingest_and_resolve(client, org.manager, VALID_PAYLOAD)["id"]

    assert client.get("/api/v1/intake/records", headers=org.agent).status_code == 403
    assert client.post(f"/api/v1/intake/records/{record_id}/discard", headers=org.agent).status_code == 403

from domain.value_objects.enums import IntakeJobStatus

UPLOAD = "/api/v1/intake/leads/batch-upload"
_HEADER = "first_name,last_name,email,company,budget,industry\n"


def _upload(client, headers, name: str, content: bytes):
    response = client.post(UPLOAD, files={"file": (name, content, "text/csv")}, headers=headers)
    assert response.status_code == 202, response.text
    return response.json()


def _job_status(client, headers, job_id: str) -> str:
    return client.get(f"/api/v1/intake/jobs/{job_id}", headers=headers).json()["status"]


def test_mixed_batch_leaves_one_promoted_and_one_rejected_in_the_inbox(client, organization):
    manager = organization().manager
    csv = (
        _HEADER + "Ana,Silva,ana@company.com,CompanyA,20000,Finance\n"
        "Mal,Formado,email-sin-arroba,CompanyB,10000,Retail\n"
    ).encode()

    accepted = _upload(client, manager, "leads.csv", csv)

    assert accepted["record_ids"] == []
    items = client.get(f"/api/v1/intake/records?job_id={accepted['job_id']}", headers=manager).json()["items"]
    by_status = {item["status"]: item for item in items}
    assert set(by_status) == {"PROMOTED", "REJECTED"}
    assert by_status["PROMOTED"]["lead_id"]
    assert by_status["REJECTED"]["errors"]


def test_an_unreadable_file_fails_the_job_without_a_500(client, organization):
    manager = organization().manager

    accepted = _upload(client, manager, "leads.xlsx", b"not a real spreadsheet")

    assert _job_status(client, manager, accepted["job_id"]) == IntakeJobStatus.FAILED.value
    assert client.get(f"/api/v1/intake/records?job_id={accepted['job_id']}", headers=manager).json()["items"] == []


def test_a_file_with_only_a_header_completes_with_zero_items(client, organization):
    manager = organization().manager

    accepted = _upload(client, manager, "leads.csv", _HEADER.encode())

    job = client.get(f"/api/v1/intake/jobs/{accepted['job_id']}", headers=manager).json()
    assert (job["status"], job["total_items"]) == ("COMPLETED", 0)


def test_a_file_over_10_mb_is_413_and_stores_nothing(direct_client, organization):
    org = organization()
    big = {"file": ("big.csv", b"x" * (10 * 1024 * 1024 + 1), "text/csv")}

    response = direct_client.post(UPLOAD, files=big, headers=org.direct)

    assert response.status_code == 413
    assert response.json() == {"error": True, "error_code": "PAYLOAD_TOO_LARGE", "message": "Request body too large"}
    assert direct_client.get("/api/v1/intake/jobs", headers=org.direct).json()["total"] == 0


def test_a_file_of_exactly_10_mb_is_accepted(direct_client, organization):
    org = organization()
    content = _HEADER.encode().ljust(10 * 1024 * 1024, b"\n")

    response = direct_client.post(UPLOAD, files={"file": ("edge.csv", content, "text/csv")}, headers=org.direct)

    assert response.status_code == 202

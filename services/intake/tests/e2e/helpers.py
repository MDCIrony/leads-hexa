VALID_PAYLOAD = {"first_name": "Ana", "last_name": "Diaz", "company": "Acme", "budget": 9000.0, "industry": "Tech"}
# Reaches lead-core unfiltered: the API has no email check, so the record is kept and rejected.
BAD_EMAIL_PAYLOAD = {**VALID_PAYLOAD, "email": "jane@@example.com"}


def ingest_and_resolve(client, headers: dict, payload: dict) -> dict:
    """Ingests one lead and returns its intake record, already processed.

    The gateway client runs the queued job before handing control back, so no
    polling is needed: the work is done by the time the POST returns."""
    accepted = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
    assert accepted.status_code == 202, accepted.text
    records = client.get(f"/api/v1/intake/records?job_id={accepted.json()['job_id']}", headers=headers)
    assert records.status_code == 200, records.text
    items = records.json()["items"]
    assert len(items) == 1, items
    return items[0]

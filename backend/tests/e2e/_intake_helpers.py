def ingest_and_resolve(client, headers: dict, payload: dict) -> dict:
    """Ingests one lead and returns its intake record, already processed.

    GatewayClient runs the queued job before handing control back, so no
    polling is needed here — the work is done by the time the POST returns.
    """
    accepted = client.post("/api/v1/intake/leads/ingest", json=payload, headers=headers)
    assert accepted.status_code == 202, accepted.text
    job_id = accepted.json()["job_id"]

    records = client.get(f"/api/v1/intake/records?job_id={job_id}", headers=headers)
    assert records.status_code == 200, records.text
    items = records.json()["items"]
    assert len(items) == 1, items
    return items[0]

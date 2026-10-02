from tests.e2e.helpers import BAD_EMAIL_PAYLOAD, VALID_PAYLOAD, ingest_and_resolve

RECORDS = "/api/v1/intake/records"


def test_rejected_payload_can_be_corrected_and_promoted_through_the_inbox(client, organization, lead_core):
    manager = organization().manager
    record_id = ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)["id"]

    listing = client.get(f"{RECORDS}?status=REJECTED", headers=manager)
    listed = next(item for item in listing.json()["items"] if item["id"] == record_id)
    assert listed["payload"]["email"] == "jane@@example.com"
    assert any(error["field"] == "email" for error in listed["errors"])

    promote = client.post(
        f"{RECORDS}/{record_id}/promote", json={"payload": {**VALID_PAYLOAD, "email": "ana@example.com"}},
        headers=manager,
    )

    assert promote.status_code == 200, promote.text
    promoted = promote.json()
    assert promoted["intake_record_id"] == record_id
    assert promoted["lead_id"]
    # The retry reused the row instead of adding one, and made exactly one lead.
    assert client.get(RECORDS, headers=manager).json()["total"] == 1
    assert len(lead_core.leads) == 1

    again = client.post(f"{RECORDS}/{record_id}/promote", json={"payload": VALID_PAYLOAD}, headers=manager)
    assert again.status_code == 400
    assert again.json()["error_code"] == "INVALID_INTAKE_TRANSITION"
    assert len(lead_core.leads) == 1


def test_promote_with_a_still_invalid_payload_stays_rejected_with_new_errors(client, organization):
    manager = organization().manager
    record_id = ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)["id"]

    promote = client.post(
        f"{RECORDS}/{record_id}/promote",
        json={"payload": {**VALID_PAYLOAD, "email": "ana@example.com", "budget": -50.0}}, headers=manager,
    )

    assert promote.status_code == 400
    assert promote.json() == {
        "error": True, "error_code": "INVALID_BUDGET", "message": "Budget must be positive",
        "intake_record_id": record_id,
    }
    record = client.get(f"{RECORDS}?status=REJECTED", headers=manager).json()["items"][0]
    assert record["errors"][0]["field"] == "budget"


def test_promotion_with_lead_core_down_is_503_and_leaves_the_record_as_it_was(client, organization, lead_core):
    manager = organization().manager
    record_id = ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)["id"]
    lead_core.down = True

    promote = client.post(f"{RECORDS}/{record_id}/promote", json={"payload": VALID_PAYLOAD}, headers=manager)

    assert promote.status_code == 503
    assert promote.json()["error_code"] == "LEAD_CORE_UNAVAILABLE"
    assert client.get(f"{RECORDS}?status=REJECTED", headers=manager).json()["total"] == 1

    lead_core.down = False
    retry = client.post(f"{RECORDS}/{record_id}/promote", json={"payload": VALID_PAYLOAD}, headers=manager)
    assert retry.status_code == 200


def test_discard_a_rejected_record(client, organization):
    manager = organization().manager
    record_id = ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)["id"]

    assert client.post(f"{RECORDS}/{record_id}/discard", headers=manager).status_code == 204

    listing = client.get(f"{RECORDS}?status=DISCARDED", headers=manager).json()
    assert [item["id"] for item in listing["items"]] == [record_id]


def test_discard_an_already_promoted_record_fails(client, organization):
    manager = organization().manager
    record_id = ingest_and_resolve(client, manager, VALID_PAYLOAD)["id"]

    discard = client.post(f"{RECORDS}/{record_id}/discard", headers=manager)

    assert discard.status_code == 400
    assert discard.json()["error_code"] == "INVALID_INTAKE_TRANSITION"


def test_listing_filters_by_status_and_paginates(client, organization):
    manager = organization().manager
    ingest_and_resolve(client, manager, VALID_PAYLOAD)
    ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)

    page = client.get(f"{RECORDS}?limit=1", headers=manager).json()
    promoted = client.get(f"{RECORDS}?status=PROMOTED", headers=manager).json()
    unknown = client.get(f"{RECORDS}?status=NOPE", headers=manager)

    assert (page["total"], len(page["items"]), page["has_more"]) == (2, 1, True)
    assert promoted["total"] == 1
    assert (unknown.status_code, unknown.json()["error_code"]) == (400, "INVALID_INTAKE_STATUS")
    assert set(page["items"][0]) == {
        "id", "source_id", "status", "payload", "errors", "received_at", "processed_at", "lead_id",
    }

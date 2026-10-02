from uuid import uuid4

URL = "/api/v1/sources"


def test_new_organization_lists_its_two_automatic_sources(client, organization):
    response = client.get(URL, headers=organization().manager)

    assert response.status_code == 200
    assert {item["kind"] for item in response.json()["items"]} == {"MANUAL_FORM", "FILE_UPLOAD"}
    assert set(response.json()["items"][0]) == {"id", "name", "kind", "field_mapping", "is_active", "created_at"}


def test_trailing_slash_is_served_without_redirect(client, organization):
    assert client.get(f"{URL}/", headers=organization().manager, follow_redirects=False).status_code == 200


def test_create_source_appears_in_listing(client, organization):
    manager = organization().manager

    response = client.post(URL, json={"name": "Landing Page", "kind": "MANUAL_FORM"}, headers=manager)

    assert response.status_code == 201
    created = response.json()
    assert created["name"] == "Landing Page"
    assert created["is_active"] is True
    assert created["id"] in {item["id"] for item in client.get(URL, headers=manager).json()["items"]}


def test_create_source_rejects_a_duplicate_name_in_the_same_organization(client, organization):
    manager = organization().manager
    body = {"name": f"Campaign {uuid4().hex[:6]}", "kind": "MANUAL_FORM"}
    assert client.post(URL, json=body, headers=manager).status_code == 201
    total_before = client.get(URL, headers=manager).json()["total"]

    second = client.post(URL, json=body, headers=manager)

    assert second.status_code == 400
    assert second.json()["error_code"] == "SOURCE_ALREADY_EXISTS"
    assert client.get(URL, headers=manager).json()["total"] == total_before


def test_the_same_source_name_is_allowed_in_different_organizations(client, organization):
    body = {"name": "Shared Name", "kind": "MANUAL_FORM"}

    assert client.post(URL, json=body, headers=organization().manager).status_code == 201
    assert client.post(URL, json=body, headers=organization().manager).status_code == 201


def test_a_source_of_another_organization_is_404_not_403(client, organization):
    owner, other = organization(), organization()
    foreign_id = client.get(URL, headers=owner.manager).json()["items"][0]["id"]

    patched = client.patch(f"{URL}/{foreign_id}", json={"is_active": False}, headers=other.manager)
    deleted = client.delete(f"{URL}/{foreign_id}", headers=other.manager)

    assert (patched.status_code, patched.json()["error_code"]) == (404, "SOURCE_NOT_FOUND")
    assert (deleted.status_code, deleted.json()["error_code"]) == (404, "SOURCE_NOT_FOUND")


def test_patch_is_active_toggles_in_both_directions(client, organization):
    manager = organization().manager
    source_id = client.post(URL, json={"name": "Toggle", "kind": "MANUAL_FORM"}, headers=manager).json()["id"]

    off = client.patch(f"{URL}/{source_id}", json={"is_active": False}, headers=manager)
    on = client.patch(f"{URL}/{source_id}", json={"is_active": True}, headers=manager)

    assert (off.status_code, off.json()["is_active"]) == (200, False)
    assert (on.status_code, on.json()["is_active"]) == (200, True)


def test_delete_a_source_without_records_is_204(client, organization):
    manager = organization().manager
    source_id = client.post(URL, json={"name": "Disposable", "kind": "MANUAL_FORM"}, headers=manager).json()["id"]

    assert client.delete(f"{URL}/{source_id}", headers=manager).status_code == 204


def test_delete_a_source_that_received_records_is_source_in_use_not_500(client, organization):
    manager = organization().manager
    payload = {"first_name": "Ana", "last_name": "Diaz", "company": "Acme", "budget": 1000.0, "industry": "retail"}
    assert client.post("/api/v1/intake/leads/ingest", json=payload, headers=manager).status_code == 202
    manual_form_id = next(
        item["id"] for item in client.get(URL, headers=manager).json()["items"] if item["kind"] == "MANUAL_FORM"
    )

    response = client.delete(f"{URL}/{manual_form_id}", headers=manager)

    assert response.status_code == 400
    assert response.json()["error_code"] == "SOURCE_IN_USE"

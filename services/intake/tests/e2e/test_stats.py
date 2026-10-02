from tests.e2e.helpers import BAD_EMAIL_PAYLOAD, VALID_PAYLOAD, ingest_and_resolve

STATS = "/api/v1/intake/stats"


def test_a_new_organization_has_nothing_waiting(client, organization):
    response = client.get(STATS, headers=organization().manager)

    assert response.status_code == 200
    assert response.json() == {"pending": 0, "rejected": 0, "pending_intake": 0}


def test_stats_count_rejected_records_and_ignore_promoted_ones(client, organization):
    manager = organization().manager
    ingest_and_resolve(client, manager, VALID_PAYLOAD)
    ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)
    ingest_and_resolve(client, manager, BAD_EMAIL_PAYLOAD)

    assert client.get(STATS, headers=manager).json() == {"pending": 0, "rejected": 2, "pending_intake": 2}


def test_stats_are_scoped_to_the_callers_organization(client, organization):
    a, b = organization(), organization()
    ingest_and_resolve(client, a.manager, BAD_EMAIL_PAYLOAD)

    assert client.get(STATS, headers=b.manager).json()["pending_intake"] == 0


def test_stats_are_manager_only(client, organization):
    assert client.get(STATS, headers=organization().agent).status_code == 403

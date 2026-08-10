from datetime import datetime, timedelta, timezone
from uuid import uuid4

import psycopg
import pytest

from domain.entities.tenant import Tenant
from infrastructure.adapters.output.persistence.raw_sql_tenant_repository import (
    RawSqlTenantRepository,
)


def _repo(test_db):
    connection_context = test_db.get_connection(autocommit=True)
    connection = connection_context.__enter__()
    return RawSqlTenantRepository(connection), connection_context


def test_saves_and_reads_back_every_field(test_db):
    repo, ctx = _repo(test_db)
    try:
        saved = repo.save(Tenant.create(name="Acme Corp"))
        found = repo.get_by_id(saved.id.value)
        assert found is not None
        assert found.name == "Acme Corp"
        assert found.slug == "acme-corp"
        assert found.is_active is True
        assert str(found.id) == str(saved.id)
    finally:
        ctx.__exit__(None, None, None)


def test_finds_by_slug(test_db):
    repo, ctx = _repo(test_db)
    try:
        repo.save(Tenant.create(name="Acme Corp"))
        assert repo.get_by_slug("acme-corp") is not None
        assert repo.get_by_slug("nope") is None
    finally:
        ctx.__exit__(None, None, None)


def test_save_updates_an_existing_row(test_db):
    repo, ctx = _repo(test_db)
    try:
        tenant = repo.save(Tenant.create(name="Acme Corp"))
        tenant.rename("Acme Global")
        tenant.deactivate()
        repo.save(tenant)

        found = repo.get_by_id(tenant.id.value)
        assert found.name == "Acme Global"
        assert found.is_active is False
        assert repo.count_all() == 1
    finally:
        ctx.__exit__(None, None, None)


def test_duplicate_slug_is_rejected_by_the_database(test_db):
    """The unique index is the real guarantee; application checks race."""
    repo, ctx = _repo(test_db)
    try:
        repo.save(Tenant.create(name="Acme Corp"))
        with pytest.raises(psycopg.errors.UniqueViolation):
            repo.save(Tenant.create(name="Acme Corp", tenant_id=uuid4()))
    finally:
        ctx.__exit__(None, None, None)


def test_listing_is_ordered_and_paginated(test_db):
    repo, ctx = _repo(test_db)
    try:
        for name in ("Alpha", "Beta", "Gamma"):
            repo.save(Tenant.create(name=name))
        assert repo.count_all() == 3
        first_page = repo.list_all(limit=2, offset=0)
        second_page = repo.list_all(limit=2, offset=2)
        assert len(first_page) == 2
        assert len(second_page) == 1
        # No overlap between pages: the ordering is deterministic.
        assert {str(t.id) for t in first_page}.isdisjoint({str(t.id) for t in second_page})
    finally:
        ctx.__exit__(None, None, None)


def test_listing_orders_newest_first(test_db):
    """Explicit timestamps avoid flakiness on systems fast enough to save all
    three within the same microsecond."""
    repo, ctx = _repo(test_db)
    try:
        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = repo.save(Tenant.create(name="Alpha", created_at=base))
        second = repo.save(Tenant.create(name="Beta", created_at=base + timedelta(minutes=1)))
        third = repo.save(Tenant.create(name="Gamma", created_at=base + timedelta(minutes=2)))
        page = repo.list_all(limit=3, offset=0)
        assert [str(t.id) for t in page] == [str(third.id), str(second.id), str(first.id)]
    finally:
        ctx.__exit__(None, None, None)


def test_counts_only_active_agents_of_that_organization(test_db):
    repo, ctx = _repo(test_db)
    try:
        tenant = repo.save(Tenant.create(name="Acme Corp"))
        other = repo.save(Tenant.create(name="Other Corp"))
        with test_db.get_connection(autocommit=True) as conn:
            for email, tid, active in (
                ("a@acme.test", str(tenant.id), True),
                ("b@acme.test", str(tenant.id), True),
                ("c@acme.test", str(tenant.id), False),
                ("d@other.test", str(other.id), True),
            ):
                conn.execute(
                    "INSERT INTO agents (id, name, email, is_active, role, tenant_id)"
                    " VALUES (%s,%s,%s,%s,%s,%s)",
                    (str(uuid4()), "X", email, active, "AGENT", tid),
                )
        assert repo.count_active_agents(tenant.id.value) == 2
    finally:
        ctx.__exit__(None, None, None)

from pathlib import Path
from uuid import uuid4

_MIGRATION = (Path(__file__).resolve().parents[3] / "migrations" / "017_advisors.sql").read_text(encoding="utf-8")


def test_the_migration_seeds_advisors_and_provisioned_tenants_and_runs_twice(test_db):
    tenant, agent_id, admin_id = uuid4(), uuid4(), uuid4()
    with test_db.get_connection(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO tenants (id, name, slug, created_at) VALUES (%s, %s, %s, now())", (tenant, "Acme", f"acme-{tenant}")
        )
        conn.execute(
            "INSERT INTO agents (id, name, email, role, is_active, tenant_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (agent_id, "Ana", f"{agent_id}@x.test", "AGENT", True, tenant),
        )
        conn.execute(
            "INSERT INTO agents (id, name, email, role, is_active, tenant_id) VALUES (%s, %s, %s, %s, %s, NULL)",
            (admin_id, "Admin", f"{admin_id}@x.test", "ADMIN", True),
        )

        conn.execute(_MIGRATION)
        conn.execute(_MIGRATION)

        advisors = conn.execute("SELECT agent_id, tenant_id, name, role, version FROM advisors").fetchall()
        assert [(r["agent_id"], r["tenant_id"], r["name"], r["role"], r["version"]) for r in advisors] == [
            (agent_id, tenant, "Ana", "AGENT", 1)]
        provisioned = conn.execute("SELECT tenant_id FROM provisioned_tenants").fetchall()
        assert [r["tenant_id"] for r in provisioned] == [tenant]


def test_no_foreign_key_points_at_the_frozen_tenants_table(test_db):
    with test_db.get_connection(autocommit=True) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM pg_constraint WHERE contype = 'f' AND confrelid = 'tenants'::regclass"
        ).fetchone()
        assert row["count"] == 0

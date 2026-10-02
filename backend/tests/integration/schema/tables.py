"""What leads_db holds once migration 019 has run, and what it no longer holds."""

LEAD_CORE_TABLES = {
    "advisors", "assignment_rules", "disqualification_rules", "leads", "outbox_events",
    "sales_groups", "schema_migrations", "scoring_rules", "webhook_configs",
}

# Copied to identity_db, notifications_db and intake_db in F2-F4; 019 drops them here.
FOREIGN_TABLES = {
    "tenants", "agents", "auth_sessions", "auth_challenges", "agent_mfa", "mfa_recovery_codes",
    "social_identities", "notifications", "lead_sources", "intake_jobs", "intake_records",
    "intake_errors", "intake_files", "provisioned_tenants", "processed_events",
}


def tables_in(conn, schema: str = "public") -> set[str]:
    rows = conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (schema,)).fetchall()
    return {row["tablename"] for row in rows}


def foreign_key_targets(conn, schema: str = "public") -> set[str]:
    rows = conn.execute(
        "SELECT target.relname FROM pg_constraint k JOIN pg_class target ON target.oid = k.confrelid"
        " WHERE k.contype = 'f' AND k.connamespace = %s::regnamespace",
        (schema,),
    ).fetchall()
    return {row["relname"] for row in rows}

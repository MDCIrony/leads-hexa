from chassis.outbox.row import OutboxRow


def envelope(row: OutboxRow, producer: str, schema_version: int = 1) -> dict:
    return {
        "event_id": str(row.id),
        "event_type": row.event_type,
        "schema_version": schema_version,
        "occurred_at": row.occurred_on.isoformat(),
        "producer": producer,
        "tenant_id": row.tenant_id,
        "aggregate_id": row.partition_key,
        "correlation_id": row.correlation_id,
        "payload": row.payload,
    }

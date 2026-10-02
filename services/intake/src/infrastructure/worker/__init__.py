"""Worker process of the intake service: the `job` and `internal` relays, the
`intake.jobs` consumer and the `intake.tenants` consumer.

Runs apart from the API so that a long job or an unreachable broker cannot hold
request handling back, and the two restart independently."""

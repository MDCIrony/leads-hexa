"""Intake worker process: the standalone consumer of `intake.jobs` (ADR-0027).

Its own compose service, not a thread inside the API process, so a container
restart mid-file does not strand the job. Run with `python -m infrastructure.intake_worker`.

Redelivery is what makes this safe to kill at any point: nothing is acked
until the job's run returns, and a run only ever reads PENDING records back."""

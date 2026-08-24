"""Not in the task's closed file list: the plan requires a test proving the
ingest endpoint falls back to BackgroundTasks when the queue is down, and no
router-level unit test file already existed to hold it. Filed here, flat
under tests/unit/infrastructure/, matching test_kafka_outbound_dispatcher.py
and the other infrastructure adapter tests next to it."""

import uuid

from fastapi import BackgroundTasks

from application.dtos.commands import ReceiveIntakeResult
from application.dtos.context import RequestContext
from infrastructure.adapters.input.api.intake_router import ingest_lead
from infrastructure.adapters.input.api.schemas import IngestLeadRequest

_TENANT = uuid.uuid4()


class _FakeReceive:
    def __init__(self, job_id: str):
        self._job_id = job_id

    def execute(self, command):
        return ReceiveIntakeResult(job_id=self._job_id, record_ids=["record-1"], status="RECEIVED")


class _FakeProcess:
    def execute(self, tenant_id, job_id):
        raise AssertionError("must run through BackgroundTasks, not called inline")


class _FakeJobQueue:
    def __init__(self, enqueued: bool):
        self._enqueued = enqueued
        self.calls = []

    def enqueue_intake_job(self, tenant_id, job_id):
        self.calls.append((tenant_id, job_id))
        return self._enqueued


def _request() -> IngestLeadRequest:
    return IngestLeadRequest(
        first_name="Jane", last_name="Doe", email="jane@example.com",
        company="Acme", budget=1000.0, industry="Tech",
    )


def _context() -> RequestContext:
    return RequestContext(actor=None, tenant_id=_TENANT)


def test_falls_back_to_background_tasks_when_the_queue_is_unreachable():
    """The one behavior worth demonstrating (per the plan): degrade, do not
    drop the client's lead because our queue is down."""
    job_id = str(uuid.uuid4())
    background = BackgroundTasks()
    process = _FakeProcess()

    ingest_lead(
        request=_request(),
        background=background,
        context=_context(),
        receive=_FakeReceive(job_id),
        process=process,
        job_queue=_FakeJobQueue(enqueued=False),
    )

    assert len(background.tasks) == 1
    task = background.tasks[0]
    assert task.func == process.execute
    assert task.args == (_TENANT, uuid.UUID(job_id))


def test_does_not_use_background_tasks_when_the_queue_accepts_the_job():
    job_id = str(uuid.uuid4())
    background = BackgroundTasks()
    job_queue = _FakeJobQueue(enqueued=True)

    ingest_lead(
        request=_request(),
        background=background,
        context=_context(),
        receive=_FakeReceive(job_id),
        process=_FakeProcess(),
        job_queue=job_queue,
    )

    assert background.tasks == []
    assert job_queue.calls == [(_TENANT, uuid.UUID(job_id))]

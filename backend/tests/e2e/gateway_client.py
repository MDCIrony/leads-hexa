"""TestClient that behaves like the gateway in front of the API (ADR-0032).

Mirrors gateway/nginx.conf: it authenticates through the internal
introspection endpoint and forwards only the resulting bearer, so e2e tests
exercise the same trust boundary the stack runs with. Tests that deliberately
talk to the app without a gateway (test_internal_auth) keep a plain TestClient.

It also stands in for the outbox worker and the intake worker (F1): after every
forwarded request it drains the internal channel into the notification
consumers and the job channel through process_job_message, in process."""
import dataclasses
import json

import httpx
from chassis.consumer import Envelope
from chassis.outbox import OutboxRow, envelope
from fastapi.testclient import TestClient

from infrastructure.adapters.input.events.notification_consumer import NotificationConsumer
from infrastructure.adapters.output.events.internal_topics import NOTIFICATION_GROUPS, topic_for
from infrastructure.intake_worker.messages import job_message, process_job_message

_INTROSPECT = "/internal/v1/auth/introspect"
_PUBLIC_PREFIX = "/api/v1/auth/"
_PUBLIC_EXACT = ("/health", "/openapi.json", "/docs")
_OPTIONAL_PATHS = ("/api/v1/agents", "/api/v1/agents/")
_UNAUTHORIZED = {"error": True, "error_code": "UNAUTHORIZED", "message": "Authentication required"}
_NOT_FOUND = {"error": True, "error_code": "NOT_FOUND", "message": "Not Found"}
# RabbitMQ's delivery limit on intake.jobs; past it the real message goes to the DLQ.
_MAX_JOB_DELIVERIES = 3


class GatewayClient(TestClient):
    def request(self, method, url, **kwargs):
        merged = self._merge_url(url)
        path = merged.path
        headers = httpx.Headers(kwargs.pop("headers", None))

        is_public = path.startswith(_PUBLIC_PREFIX) or path in _PUBLIC_EXACT
        if not is_public and not path.startswith("/api/v1/"):
            return httpx.Response(404, json=_NOT_FOUND, request=httpx.Request(method, merged))

        if is_public:
            # Public routes see everything but a client-supplied bearer or key.
            for name in ("authorization", "x-api-key"):
                headers.pop(name, None)
            return self._forward(method, url, headers=headers, **kwargs)

        introspection_headers = {
            name: headers[name] for name in ("cookie", "x-api-key") if name in headers
        }
        introspection = super().request(
            "GET", _INTROSPECT,
            params={"optional": "true"} if path in _OPTIONAL_PATHS else None,
            headers=introspection_headers, cookies=kwargs.get("cookies"),
        )
        if introspection.status_code == 401:
            return httpx.Response(401, json=_UNAUTHORIZED, request=httpx.Request(method, merged))
        if introspection.status_code not in (200, 204):
            return introspection

        for name in ("authorization", "x-api-key"):
            headers.pop(name, None)
        if introspection.status_code == 200:
            headers["Authorization"] = f"Bearer {introspection.headers['X-Internal-Token']}"
        # An empty Cookie header stops httpx from adding the client's jar: the
        # service must never see the session cookie.
        headers["Cookie"] = ""
        kwargs.pop("cookies", None)
        return self._forward(method, url, headers=headers, **kwargs)

    def _forward(self, method, url, **kwargs):
        response = super().request(method, url, **kwargs)
        self._drain_internal()
        # Processing a job writes internal events of its own, hence the second pass.
        if self._drain_jobs():
            self._drain_internal()
        return response

    def _drain_jobs(self) -> bool:
        """What the relay plus RabbitMQ plus the intake worker will do, minus the broker.

        A nack is redelivered up to the queue's limit and then dropped, as the
        dead-letter queue would. Returns whether any job ran."""
        container = getattr(self.app.state, "container", None)
        if container is None:
            return False
        ran = False
        while True:
            with container.unit_of_work() as uow:
                entries = uow.outbox.list_unpublished("job", 100)
            if not entries:
                return ran
            for entry in entries:
                message = json.loads(json.dumps(job_message(OutboxRow(**dataclasses.asdict(entry)))))
                for _ in range(_MAX_JOB_DELIVERIES):
                    if process_job_message(container, message) == "ack":
                        break
                with container.unit_of_work() as uow:
                    uow.outbox.mark_published(entry.id)
                ran = True

    def _drain_internal(self) -> None:
        """What the relay plus the Kafka consumers will do, minus the broker.

        The envelope goes through bytes and back, the same path a real message
        takes. Identity state has no consumer in F1, so it is only marked."""
        container = getattr(self.app.state, "container", None)
        if container is None:
            return
        consumers = {
            topic: NotificationConsumer(container.unit_of_work, group)
            for group, topic in NOTIFICATION_GROUPS.items()
        }
        while True:
            with container.unit_of_work() as uow:
                entries = uow.outbox.list_unpublished("internal", 100)
            if not entries:
                return
            for entry in entries:
                row = OutboxRow(**dataclasses.asdict(entry))
                consumer = consumers.get(topic_for(row))
                if consumer is not None:
                    consumer(Envelope.from_bytes(json.dumps(envelope(row, "lead-core")).encode()))
                with container.unit_of_work() as uow:
                    uow.outbox.mark_published(entry.id)

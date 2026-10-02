"""Request correlation shared by every service: one id per request, the same
in the gateway access log, in each service's logs and in the response."""
import logging
import os
import re
import sys
import uuid
from contextvars import ContextVar

_SAFE_ID = re.compile(r"[A-Za-z0-9._-]{1,128}")
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s"

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdMiddleware:
    """Pure ASGI so chassis does not depend on a web framework."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        # Only an id that is safe to write into a log line is trusted.
        request_id = incoming if _SAFE_ID.fullmatch(incoming) else uuid.uuid4().hex
        token = request_id_var.set(request_id)

        async def send_with_id(message):
            if message["type"] == "http.response.start":
                headers = [(k, v) for k, v in message.get("headers", []) if k.lower() != b"x-request-id"]
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_id)
        # Not in a `finally`: on an unhandled error the outer ServerErrorMiddleware
        # logs the 500 after this frame unwinds and still needs the id. Nothing
        # leaks, since the server runs each request in its own copied context.
        request_id_var.reset(token)


class RequestIdLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str | None = None) -> None:
    """One line per record on stdout, tagged with the current request id."""
    logging.basicConfig(
        level=(level or os.getenv("LOG_LEVEL", "INFO")).upper(),
        format=LOG_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    for handler in logging.getLogger().handlers:
        handler.addFilter(RequestIdLogFilter())
    # uvicorn's own handlers know nothing of the request id; through the root
    # handler its access lines carry it, which is what proves the id crossed a hop.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        server_logger = logging.getLogger(name)
        server_logger.handlers.clear()
        server_logger.propagate = True
    # Every JWKS refresh would otherwise log an INFO line.
    logging.getLogger("httpx").setLevel(logging.WARNING)

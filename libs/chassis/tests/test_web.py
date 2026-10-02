import asyncio
import logging

import pytest

from chassis.web import RequestIdLogFilter, RequestIdMiddleware, request_id_var


def _run(headers):
    seen = {}

    async def app(scope, receive, send):
        seen["inside"] = request_id_var.get()
        await send({"type": "http.response.start", "status": 200,
                    "headers": [(b"x-request-id", b"upstream-value")]})
        await send({"type": "http.response.body", "body": b""})

    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request"}

    scope = {"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}
    asyncio.run(RequestIdMiddleware(app)(scope, receive, send))
    response_ids = [v.decode() for k, v in sent[0]["headers"] if k == b"x-request-id"]
    return seen["inside"], response_ids


def test_valid_incoming_id_is_kept_and_echoed_once():
    inside, echoed = _run({"x-request-id": "abc-123_x.y"})
    assert inside == "abc-123_x.y"
    assert echoed == ["abc-123_x.y"]


def test_missing_id_is_generated():
    inside, echoed = _run({})
    assert inside not in ("", "-")
    assert echoed == [inside]


@pytest.mark.parametrize("hostile", ["has space", "line\nbreak", "x" * 129, "semi;colon", "abc\n"])
def test_hostile_id_is_replaced(hostile):
    inside, echoed = _run({"x-request-id": hostile})
    assert inside != hostile
    assert echoed == [inside]


def test_context_is_reset_after_the_request():
    # Same coroutine for the call and the read: asyncio.run copies the context,
    # so reading outside would pass even without the reset.
    async def scenario():
        async def app(scope, receive, send):
            pass

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            pass

        scope = {"type": "http", "headers": [(b"x-request-id", b"abc")]}
        await RequestIdMiddleware(app)(scope, receive, send)
        return request_id_var.get()

    assert asyncio.run(scenario()) == "-"


def test_request_id_survives_an_unhandled_error():
    # ServerErrorMiddleware sits outside user middlewares and logs the 500 after
    # this one has unwound, so the id must still be readable by the outer handler.
    async def scenario():
        async def app(scope, receive, send):
            raise RuntimeError("boom")

        async def receive():
            return {"type": "http.request"}

        async def send(message):
            pass

        scope = {"type": "http", "headers": [(b"x-request-id", b"abc")]}
        try:
            await RequestIdMiddleware(app)(scope, receive, send)
        except RuntimeError:
            return request_id_var.get()

    assert asyncio.run(scenario()) == "abc"


def test_log_filter_injects_current_id():
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
    token = request_id_var.set("rid-1")
    try:
        assert RequestIdLogFilter().filter(record) is True
    finally:
        request_id_var.reset(token)
    assert record.request_id == "rid-1"

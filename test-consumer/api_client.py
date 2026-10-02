"""Calls to the lead router, always through the gateway.

Split from app.py so the inbox logic and the HTTP plumbing can each be read on
their own."""
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

from fastapi import HTTPException

LOGGER = logging.getLogger("inbox")
API_BASE = os.getenv("LEADS_API_BASE", "http://backend:8000/api/v1")


def new_session():
    """An opener with its own cookie jar: the session lives only as long as it does."""
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def call_api(method: str, path: str, *, opener=None, api_key=None, form=None, timeout=20):
    url = f"{API_BASE}{path}"
    headers, data = {}, None
    if api_key:
        headers["X-Api-Key"] = api_key
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with (opener or urllib.request.build_opener()).open(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw)
        except ValueError:
            return error.code, {"detail": raw.decode(errors="replace")}
    except urllib.error.URLError as error:
        raise HTTPException(502, f"no se alcanza {url}: {error.reason}")


def logout(session) -> None:
    """Best effort: a session that cannot be closed expires on its own, and
    failing here would discard a credential the router has already rotated."""
    try:
        call_api("POST", "/auth/logout", opener=session)
    except Exception as error:
        LOGGER.warning("logout failed, the session will expire by itself: %s", getattr(error, "detail", error))

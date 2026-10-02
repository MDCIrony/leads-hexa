import logging
from typing import Callable

import httpx
from chassis.auth import ServiceTokenClient, ServiceTokenUnavailable
from chassis.web import request_id_var

from application.ports.output.admissions import AdmissionUnavailable

_LOGGER = logging.getLogger(__name__)

# Tighter than the shared client's timeout: the token lock is held across this call,
# so a hung identity must not stall every admission for the admission timeout.
_TOKEN_TIMEOUT_SECONDS = 2.0


def correlated_post(post: Callable[..., httpx.Response]) -> Callable[..., httpx.Response]:
    """The token request carries the caller's request id, like the call it precedes."""
    return lambda url, **kwargs: post(
        url, headers=correlation_header(), timeout=_TOKEN_TIMEOUT_SECONDS, **kwargs,
    )


def correlation_header() -> dict[str, str]:
    # "-" is the ContextVar's default, not a request id: sending it would
    # make unrelated calls look like one request in lead-core's logs.
    request_id = request_id_var.get()
    return {} if request_id == "-" else {"X-Request-Id": request_id}


def unavailable(reason: str) -> AdmissionUnavailable:
    # Only the reason: never the token, the secret or lead-core's body.
    _LOGGER.warning("lead-core unavailable for admission: %s", reason)
    return AdmissionUnavailable(reason)


class LeadCoreClient:
    """Authenticated calls to lead-core's internal API; anything but a 200 is AdmissionUnavailable."""

    def __init__(self, lead_core_url: str, tokens: ServiceTokenClient, client: httpx.Client) -> None:
        self._base = lead_core_url.rstrip("/") + "/internal/v1/admissions"
        self._tokens = tokens
        self._client = client

    def send(self, method: str, **kwargs) -> httpx.Response:
        try:
            headers = {"Authorization": f"Bearer {self._tokens.token()}", **correlation_header()}
            response = self._client.request(method, self._base, headers=headers, **kwargs)
        except (ServiceTokenUnavailable, httpx.HTTPError) as error:
            raise unavailable(type(error).__name__) from None
        if response.status_code == 401:
            # Refused, not expired (a rotated key, a changed client entry): the
            # next call fetches a fresh token instead of reusing this one for minutes.
            self._tokens.invalidate()
        if response.status_code != 200:
            raise unavailable(f"answered {response.status_code}")
        return response

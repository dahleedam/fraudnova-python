"""Shared test helpers: a MockTransport-backed httpx client factory."""

import json
from collections import deque
from typing import Any, Callable, Optional, Union

import httpx
import pytest

Queued = Union[httpx.Response, Exception]
ClientFactory = Callable[..., "tuple[httpx.Client, list[httpx.Request]]"]


def json_response(
    status: int, body: Any, headers: Optional[dict[str, str]] = None
) -> httpx.Response:
    """Build an httpx.Response with a JSON-encoded body."""
    return httpx.Response(status, content=json.dumps(body).encode(), headers=headers)


@pytest.fixture
def make_http_client() -> ClientFactory:
    """Return `make(*responses) -> (httpx.Client, sent_requests)`.

    Each item is either an `httpx.Response`, returned for the next request, or an `Exception`
    instance, raised for it (e.g. `httpx.ConnectTimeout("boom")`). Running out of queued items
    raises `AssertionError("no more responses")`. Every request is appended to `sent_requests`.
    """

    def make(*responses: Queued) -> "tuple[httpx.Client, list[httpx.Request]]":
        queue: deque[Queued] = deque(responses)
        sent: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            sent.append(request)
            if not queue:
                raise AssertionError("no more responses")
            item = queue.popleft()
            if isinstance(item, Exception):
                raise item
            return item

        return httpx.Client(transport=httpx.MockTransport(handler)), sent

    return make

import json
from typing import Optional

import httpx
import pytest

from fraudnova._transport import Transport
from fraudnova.exceptions import (
    InsufficientCreditsError,
    RateLimitError,
    TransportError,
    UnexpectedResponseError,
    UpstreamError,
)
from fraudnova.retry import RetryPolicy
from tests.conftest import ClientFactory, json_response

KEY = "fn_test_key_1234567890"
BASE = "https://fraudnova.com/api/v1/"
OK = {"success": True}


def transport(client: Optional[httpx.Client], retry: Optional[RetryPolicy] = None) -> Transport:
    return Transport(KEY, BASE, 30.0, retry, client)


def test_get_builds_url_headers_and_query(make_http_client: ClientFactory) -> None:
    client, sent = make_http_client(json_response(200, OK))
    t = transport(client)
    assert t.base_url == "https://fraudnova.com/api/v1"
    assert t.get("/check", {"ip": "8.8.8.8", "mobile": "true"}) == OK
    request = sent[0]
    assert str(request.url) == "https://fraudnova.com/api/v1/check?ip=8.8.8.8&mobile=true"
    assert request.method == "GET"
    assert request.headers["Accept"] == "application/json"
    assert request.headers["Authorization"] == f"Bearer {KEY}"
    assert request.headers["User-Agent"].startswith("fraudnova-python/1.0.0 python/")


def test_unauthenticated_get_sends_no_authorization(make_http_client: ClientFactory) -> None:
    client, sent = make_http_client(json_response(200, OK))
    transport(client).get("/my-ip", authenticated=False)
    assert "Authorization" not in sent[0].headers


def test_post_sends_json_body(make_http_client: ClientFactory) -> None:
    client, sent = make_http_client(json_response(200, OK))
    payload = {"ips": ["8.8.8.8", None], "mobile": True}
    transport(client).post("/check/batch", payload)
    assert sent[0].method == "POST"
    assert sent[0].headers["Content-Type"] == "application/json"
    assert sent[0].headers["Authorization"] == f"Bearer {KEY}"
    assert json.loads(sent[0].content) == payload


def test_non_2xx_maps_to_api_error(make_http_client: ClientFactory) -> None:
    client, _ = make_http_client(
        json_response(402, {"success": False, "message": "Insufficient credits."}),
        json_response(
            429,
            {"success": False, "message": "Too many requests."},
            {"Retry-After": "3"},
        ),
    )
    t = transport(client)
    with pytest.raises(InsufficientCreditsError):
        t.get("/check")
    with pytest.raises(RateLimitError) as info:
        t.get("/check")
    assert info.value.retry_after == 3


@pytest.mark.parametrize("body", ['{"success": false}', "not json", "[]"])
def test_2xx_without_success_true_is_unexpected(make_http_client: ClientFactory, body: str) -> None:
    client, _ = make_http_client(httpx.Response(200, content=body.encode()))
    with pytest.raises(UnexpectedResponseError) as info:
        transport(client).get("/check")
    assert info.value.status_code == 200


def test_transport_error_wraps_httpx(make_http_client: ClientFactory) -> None:
    boom = httpx.ConnectTimeout("boom")
    client, _ = make_http_client(boom)
    with pytest.raises(TransportError) as info:
        transport(client).get("/check")
    assert info.value.__cause__ is boom
    assert KEY not in str(info.value)
    assert "boom" in str(info.value)


def _policy(sleeps: list[float], max_attempts: int = 3) -> RetryPolicy:
    return RetryPolicy(max_attempts=max_attempts, sleeper=sleeps.append)


def test_retry_on_429_then_success(make_http_client: ClientFactory) -> None:
    client, sent = make_http_client(
        json_response(429, {"success": False, "message": "Too many concurrent requests."}),
        json_response(429, {"success": False, "message": "Rate limited."}, {"Retry-After": "2"}),
        json_response(200, OK),
    )
    sleeps: list[float] = []
    assert transport(client, _policy(sleeps)).get("/check") == OK
    assert len(sent) == 3
    assert sleeps == [1.0, 2.0]


def test_retry_gives_up_after_max_attempts(make_http_client: ClientFactory) -> None:
    rate = json_response(429, {"success": False, "message": "Rate limited."})
    rate2 = json_response(429, {"success": False, "message": "Rate limited."})
    client, sent = make_http_client(rate, rate2)
    sleeps: list[float] = []
    with pytest.raises(RateLimitError):
        transport(client, _policy(sleeps, max_attempts=2)).get("/check")
    assert len(sent) == 2
    assert sleeps == [5.0]


def test_no_retry_without_policy(make_http_client: ClientFactory) -> None:
    client, sent = make_http_client(json_response(429, {"success": False, "message": "No."}))
    with pytest.raises(RateLimitError):
        transport(client).get("/check")
    assert len(sent) == 1


def test_only_429_is_retried(make_http_client: ClientFactory) -> None:
    client, sent = make_http_client(
        json_response(503, {"success": False, "message": "Upstream lookup failed."})
    )
    sleeps: list[float] = []
    with pytest.raises(UpstreamError):
        transport(client, _policy(sleeps)).get("/check")
    assert len(sent) == 1
    assert sleeps == []


def test_close_only_closes_owned_client(
    make_http_client: ClientFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    injected, _ = make_http_client()
    t = transport(injected)
    assert t.owns_client is False
    t.close()
    assert injected.is_closed is False

    owned, _ = make_http_client(json_response(200, OK))
    monkeypatch.setattr(httpx, "Client", lambda **_kwargs: owned)
    t2 = transport(None)
    assert t2.owns_client is True
    t2.get("/check")
    t2.close()
    assert owned.is_closed is True
    t2.close()  # idempotent


def test_close_without_ever_building_client_is_safe() -> None:
    t = transport(None)
    t.close()
    assert t.owns_client is True


def test_default_client_uses_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    real_client = httpx.Client

    def fake_client(**kwargs: object) -> httpx.Client:
        seen.update(kwargs)
        return real_client(transport=httpx.MockTransport(lambda request: json_response(200, OK)))

    monkeypatch.setattr(httpx, "Client", fake_client)
    Transport(KEY, BASE, 12.0, None, None).get("/check")
    assert seen["timeout"] == httpx.Timeout(12.0, connect=10.0)

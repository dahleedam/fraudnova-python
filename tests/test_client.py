import json
from typing import Any, Callable

import httpx
import pytest

import fraudnova
from fraudnova import (
    BATCH_MAX,
    Client,
    EmailResult,
    InsufficientCreditsError,
    InvalidArgumentError,
    IpResult,
    PhoneResult,
    UnexpectedResponseError,
)
from tests.conftest import ClientFactory, json_response

KEY = "fn_test_key_1234567890"


def ok(data: dict[str, Any], credits: int = 5) -> httpx.Response:
    return json_response(200, {"success": True, "data": data, "credits_remaining": credits})


def echo_batch(kind: str, subjects: list[Any], credits: int) -> httpx.Response:
    results = [
        {kind: s, "success": True, "data": {"fraud_score": 1}} for s in subjects if s is not None
    ]
    return json_response(200, {"success": True, "results": results, "credits_remaining": credits})


def test_rejects_empty_key_and_bad_base_url() -> None:
    with pytest.raises(InvalidArgumentError):
        Client("   ")
    with pytest.raises(InvalidArgumentError):
        Client(KEY, base_url="ftp://x")
    Client(KEY, base_url="HTTPS://example.com/api/").close()


def test_repr_masks_key() -> None:
    c = Client(KEY)
    assert "fn_…7890" in repr(c)
    assert KEY not in repr(c)
    assert repr(Client("fn_short123")).startswith("Client(api_key='fn_…'")
    c.close()


def test_check_ip_sends_query_and_parses(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client(ok({"fraud_score": 80}, 9))
    c = Client(KEY, http_client=http)
    r = c.check_ip(" 8.8.8.8 ", strictness=2, mobile=True, user_agent="UA x", user_language="en-US")
    assert isinstance(r, IpResult)
    assert r.fraud_score == 80
    assert r.credits_remaining == 9
    req = sent[0]
    assert req.url.path.endswith("/check")
    assert dict(req.url.params) == {
        "ip": "8.8.8.8",
        "strictness": "2",
        "mobile": "true",
        "user_agent": "UA x",
        "user_language": "en-US",
    }
    assert req.headers["Authorization"] == f"Bearer {KEY}"


def test_check_ip_omits_unset_options(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client(ok({}), ok({}))
    c = Client(KEY, http_client=http)
    c.check_ip("8.8.8.8")
    assert sent[0].url.query == b"ip=8.8.8.8"
    c.check_ip("8.8.8.8", mobile=False)
    assert dict(sent[1].url.params)["mobile"] == "false"


def test_check_ip_rejects_bad_strictness_and_empty_ip(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client()
    c = Client(KEY, http_client=http)
    for bad in (-1, 4, 2.0, True):
        with pytest.raises(InvalidArgumentError):
            c.check_ip("8.8.8.8", strictness=bad)  # type: ignore[arg-type]
    with pytest.raises(InvalidArgumentError):
        c.check_ip("  ")
    assert sent == []


def test_check_email_and_phone(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client(ok({"valid": True}), ok({"VOIP": True}), ok({}))
    c = Client(KEY, http_client=http)
    assert isinstance(c.check_email(" a@b.co "), EmailResult)
    assert dict(sent[0].url.params) == {"email": "a@b.co"}
    assert isinstance(c.check_phone("18176791808", country=" us "), PhoneResult)
    assert sent[1].url.path.endswith("/check/phone")
    assert dict(sent[1].url.params) == {"phone": "18176791808", "country": "US"}
    c.check_phone("18176791808")
    assert "country" not in dict(sent[2].url.params)
    with pytest.raises(InvalidArgumentError):
        c.check_email("")
    with pytest.raises(InvalidArgumentError):
        c.check_phone(" ")


def test_check_ips_chunks_by_100(make_http_client: ClientFactory) -> None:
    ips = [f"10.0.{i // 250}.{i % 250}" for i in range(250)]
    http, sent = make_http_client(
        echo_batch("ip", ips[:100], 30),
        echo_batch("ip", ips[100:200], 20),
        echo_batch("ip", ips[200:], 10),
    )
    c = Client(KEY, http_client=http)
    result = c.check_ips(ips, strictness=2, mobile=True)
    assert len(sent) == 3
    bodies = [json.loads(r.content) for r in sent]
    assert [len(b["ips"]) for b in bodies] == [100, 100, 50]
    assert all(r.url.path.endswith("/check/batch") for r in sent)
    assert bodies[0]["strictness"] == 2
    assert bodies[0]["mobile"] is True
    assert [i.subject for i in result.items] == ips
    assert result.credits_remaining == 10
    assert BATCH_MAX == 100


def test_check_emails_and_phones_bodies(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client(echo_batch("email", ["a@b.co"], 3), echo_batch("phone", ["1"], 2))
    c = Client(KEY, http_client=http)
    c.check_emails(["a@b.co"])
    c.check_phones(["1"], country="us")
    assert sent[0].url.path.endswith("/check/email/batch")
    assert json.loads(sent[0].content) == {"emails": ["a@b.co"]}
    assert sent[1].url.path.endswith("/check/phone/batch")
    assert json.loads(sent[1].content) == {"phones": ["1"], "country": "US"}


def test_batch_rejects_empty_and_non_string_items(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client(echo_batch("ip", ["a"], 1))
    c = Client(KEY, http_client=http)
    with pytest.raises(InvalidArgumentError):
        c.check_ips([])
    with pytest.raises(InvalidArgumentError, match="1"):
        c.check_ips(["a", 5])  # type: ignore[list-item]
    assert sent == []
    c.check_ips([" a ", None, ""])
    assert json.loads(sent[0].content)["ips"] == ["a", None, ""]


def test_batch_error_on_later_chunk_propagates(make_http_client: ClientFactory) -> None:
    items = [f"1.1.1.{i}" for i in range(101)]
    http, sent = make_http_client(
        echo_batch("ip", items[:100], 5),
        json_response(402, {"success": False, "message": "Insufficient credits"}),
    )
    c = Client(KEY, http_client=http)
    with pytest.raises(InsufficientCreditsError):
        c.check_ips(items)
    assert len(sent) == 2


def test_batch_stops_when_balance_reaches_zero(make_http_client: ClientFactory) -> None:
    ips = [f"10.1.{i // 250}.{i % 250}" for i in range(249)] + [None]
    http, sent = make_http_client(echo_batch("ip", ips[:100], 0))
    c = Client(KEY, http_client=http)
    result = c.check_ips(ips)
    assert len(sent) == 1
    assert len(result.items) == 250
    assert all(i.success for i in result.items[:100])
    rest = result.items[100:]
    assert all(not i.success and i.result is None for i in rest)
    assert all(i.is_insufficient_credits() for i in rest)
    assert [i.subject for i in rest] == [*ips[100:249], ""]
    assert result.credits_remaining == 0


def test_batch_continues_while_credits_remain(make_http_client: ClientFactory) -> None:
    ips = [f"10.2.0.{i}" for i in range(150)]
    http, sent = make_http_client(echo_batch("ip", ips[:100], 5), echo_batch("ip", ips[100:], 0))
    c = Client(KEY, http_client=http)
    result = c.check_ips(ips)
    assert len(sent) == 2
    assert all(i.success for i in result.items)
    assert result.credits_remaining == 0


def test_batch_rejects_bare_string(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client()
    c = Client(KEY, http_client=http)
    with pytest.raises(InvalidArgumentError):
        c.check_ips("8.8.8.8")
    with pytest.raises(InvalidArgumentError):
        c.check_emails(b"a@b.co")  # type: ignore[arg-type]
    with pytest.raises(InvalidArgumentError):
        c.check_phones("15551234567")
    assert sent == []


def test_balance_and_my_ip(make_http_client: ClientFactory) -> None:
    http, sent = make_http_client(
        json_response(200, {"success": True, "credits_remaining": 123}),
        json_response(200, {"success": True, "ip": "203.0.113.9"}),
    )
    c = Client(KEY, http_client=http)
    assert c.balance() == 123
    assert c.my_ip() == "203.0.113.9"
    assert "Authorization" in sent[0].headers
    assert "Authorization" not in sent[1].headers


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda c: c.check_ip("1.1.1.1"), "Missing data"),
        (lambda c: c.check_ips(["1.1.1.1"]), "Missing results"),
        (lambda c: c.balance(), "Missing credits_remaining"),
        (lambda c: c.my_ip(), "Missing ip"),
    ],
)
def test_missing_data_is_unexpected_response(
    make_http_client: ClientFactory, call: Callable[[Client], Any], message: str
) -> None:
    http, _ = make_http_client(json_response(200, {"success": True}))
    with pytest.raises(UnexpectedResponseError) as info:
        call(Client(KEY, http_client=http))
    assert info.value.api_message == message


def test_context_manager_closes_owned_client(make_http_client: ClientFactory) -> None:
    with Client(KEY) as c:
        owned = c._transport._http()
        assert owned.is_closed is False
    assert owned.is_closed is True
    http, _ = make_http_client()
    with Client(KEY, http_client=http):
        pass
    assert http.is_closed is False


def test_public_exports() -> None:
    names = [
        "Client", "RetryPolicy", "DEFAULT_BASE_URL", "BATCH_MAX", "IpResult", "EmailResult",
        "PhoneResult", "DateInfo", "BatchItem", "BatchResult", "FraudNovaError",
        "InvalidArgumentError", "TransportError", "ApiError", "AuthenticationError",
        "InsufficientCreditsError", "AccountSuspendedError", "ValidationError", "RateLimitError",
        "UpstreamError", "UnexpectedResponseError", "__version__",
    ]  # fmt: skip
    for name in names:
        assert name in fraudnova.__all__
        assert hasattr(fraudnova, name)


def test_my_ip_rejects_empty_ip(make_http_client: ClientFactory) -> None:
    http, _ = make_http_client(json_response(200, {"success": True, "ip": ""}))
    with pytest.raises(UnexpectedResponseError) as info:
        Client(KEY, http_client=http).my_ip()
    assert info.value.api_message == "Missing ip"

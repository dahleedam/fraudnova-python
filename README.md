# fraudnova

[FraudNova](https://fraudnova.com) is a fraud-detection API. It returns a fraud score and risk flags for any IP address, email address or phone number, so your application can decide whether to accept, review or block a signup, lead or order. This is the official Python client.

[![CI](https://github.com/dahleedam/fraudnova-python/actions/workflows/ci.yml/badge.svg)](https://github.com/dahleedam/fraudnova-python/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/fraudnova)](https://pypi.org/project/fraudnova/)
[![Python versions](https://img.shields.io/pypi/pyversions/fraudnova)](https://pypi.org/project/fraudnova/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Requirements

- Python 3.9 or later
- [httpx](https://www.python-httpx.org/), installed automatically

## Installation

```bash
pip install fraudnova
```

You need an API key. [Register](https://fraudnova.com/register) to get free trial credits, then create a key at [fraudnova.com/dashboard/api-keys](https://fraudnova.com/dashboard/api-keys). The key starts with `fn_` and is shown once, so copy it right away.

## Quickstart

```python
import fraudnova

client = fraudnova.Client("fn_your_api_key")
result = client.check_ip("8.8.8.8")
if result.flagged():
    ...  # review or block
print(result.fraud_score)
```

## Checking IP addresses, emails and phone numbers

```python
import fraudnova

client = fraudnova.Client("fn_your_api_key")

ip = client.check_ip("8.8.8.8")
email = client.check_email("someone@example.com")
phone = client.check_phone("+1 817 679 1808")
phone = client.check_phone("8176791808", country="US")  # optional two-letter country hint
```

`check_ip()` takes optional keyword arguments. Leave one out to use the API default.

```python
result = client.check_ip(
    visitor_ip,
    strictness=1,  # 0 = lenient, 3 = strict
    mobile=False,  # the request comes from a mobile device
    user_agent=request.headers.get("User-Agent"),  # enables the device and browser fields
    user_language=request.headers.get("Accept-Language", "").split(",")[0].strip() or None,
)
```

`user_language` takes a short language tag such as `en-US`, not the whole `Accept-Language` header, so the example sends only the first tag.

An empty value, or a `strictness` that is not an integer from 0 to 3, raises `fraudnova.InvalidArgumentError` before any request is sent.

## Batch checks

`check_ips()`, `check_emails()` and `check_phones()` score a list of values. The list can be any length: the client splits it into requests of 100 (`fraudnova.BATCH_MAX`) and joins the answers in input order.

```python
batch = client.check_ips(ips)

for item in batch.successful():
    print(item.subject, item.result.fraud_score)

for item in batch.failed():
    print(item.subject, "failed:", item.error)

print("Credits left:", batch.credits_remaining)
```

`check_ips()` takes the same keyword options as `check_ip()`, and `check_phones()` takes one `country` hint for the whole batch. `BatchResult` is iterable and supports `len()` and indexing; each `BatchItem` has `subject`, `success`, `result` (an `IpResult`, `EmailResult` or `PhoneResult`, or `None` on failure) and `error`. `has_failures()` tells you whether any item failed.

If a request after the first raises an exception, for example `InsufficientCreditsError`, the exception propagates and the requests that already succeeded stay billed. If you need control over each request, slice the list yourself:

```python
for start in range(0, len(ips), fraudnova.BATCH_MAX):
    batch = client.check_ips(ips[start : start + fraudnova.BATCH_MAX])
    ...  # handle this request's result before sending the next
```

Items must be strings or `None`; any other type raises `InvalidArgumentError` before the request is sent. One bad value never fails the batch, so an empty string or `None` comes back as a failed item. A failed item carries one of these error codes:

| `error` | Helper | Meaning |
| --- | --- | --- |
| `invalid_ip`, `invalid_email`, `invalid_phone` | `is_invalid()` | The value is not a valid IP address, email address or phone number. |
| `insufficient_credits` | `is_insufficient_credits()` | Your balance ran out partway through the batch. |
| `upstream_failed` | `is_upstream_failed()` | The lookup failed. The item was not charged. |

## Results

`check_ip()`, `check_email()` and `check_phone()` return an `IpResult`, `EmailResult` or `PhoneResult`. Each has the API's fields as snake_case attributes, for example `fraud_score`, `recent_abuse` and `country_code`. `fraud_score` is always an integer from 0 to 100; every other field is optional (`None`), because the API does not return every field for every check.

```python
ip = client.check_ip("8.8.8.8")
ip.proxy  # Optional[bool]
ip.vpn  # Optional[bool]
ip.country_code  # Optional[str], for example "US"
ip.isp  # Optional[str] (API field ISP)
ip.asn  # Optional[int] (API field ASN)

email = client.check_email("someone@example.com")
email.disposable  # Optional[bool]
email.deliverability  # Optional[str]
email.first_seen  # Optional[DateInfo], also domain_age

phone = client.check_phone("+18176791808")
phone.voip  # Optional[bool] (API field VOIP)
phone.line_type  # Optional[str]
phone.carrier  # Optional[str]
```

The email dates `first_seen` and `domain_age` are `DateInfo` objects with `human`, `timestamp` and `iso`.

`to_dict()` returns the full API response for that check, with the original field names, including any field the client does not map to an attribute:

```python
fields = client.check_ip("8.8.8.8").to_dict()
# {"fraud_score": 20, "proxy": False, "ISP": "Google", ...}
```

`credits_remaining` holds your balance after the check. It is `None` on results inside a batch; read `BatchResult.credits_remaining` there instead.

## The `flagged()` helper

`flagged()` returns `True` when the `fraud_score` is at or above a risk threshold (default 75), or when any of a set of fields is `True`. `flag_reasons()` lists which of those fired, for example `["fraud_score", "proxy"]`. Both take the same two optional arguments, `risk_threshold` and `flag_on`.

| Check | Fields checked by default |
| --- | --- |
| IP address | `proxy`, `vpn`, `tor` |
| Email address | `disposable` |
| Phone number | `VOIP`, `risky` |

Pass your own threshold and fields with the raw API field names (`VOIP`, not `voip`):

```python
result = client.check_phone("+18176791808")

if result.flagged(risk_threshold=85, flag_on=["VOIP", "risky", "recent_abuse"]):
    reasons = result.flag_reasons(85, ["VOIP", "risky", "recent_abuse"])
    ...
```

The defaults are available as `IpResult.DEFAULT_FLAG_ON`, `EmailResult.DEFAULT_FLAG_ON` and `PhoneResult.DEFAULT_FLAG_ON`.

## Balance and your IP

```python
credits = client.balance()  # int, costs no credits
ip = client.my_ip()  # str, the public IP your server calls from; no API key needed
```

## Errors

Every exception the client raises is a `fraudnova.FraudNovaError`, so one `except` handles them all:

```python
from fraudnova import FraudNovaError, InsufficientCreditsError

try:
    result = client.check_ip(visitor_ip)
except InsufficientCreditsError:
    ...  # buy a credit pack in the FraudNova dashboard
except FraudNovaError as error:
    ...  # log it and let the request through, or hold it for review
```

| Exception | Status | When |
| --- | --- | --- |
| `AuthenticationError` | 401 | The API key is missing, invalid or revoked. |
| `InsufficientCreditsError` | 402 | Your balance is too low for the check. |
| `AccountSuspendedError` | 403 | The account is suspended. |
| `ValidationError` | 422 | The API rejected the request parameters. |
| `RateLimitError` | 429 | Too many requests, or too many checks in flight at once. `retry_after` and `is_concurrency_limit` tell you which. |
| `UpstreamError` | 502, 503, 504 | The lookup failed. On a 503 the credit is refunded automatically and `credit_refunded` is `True`. |
| `UnexpectedResponseError` | 2xx | The response could not be read as a FraudNova response. |
| `ApiError` | any other error status | Base class of every exception with a status. `status_code`, `api_message` and `body` are on all of them. A 401, 402, 403 or 422 whose body is not a FraudNova JSON response (for example a proxy error page) is a plain `ApiError`. |
| `TransportError` | none | The HTTP client failed, for example a timeout or DNS error. The original exception is `__cause__`. |
| `InvalidArgumentError` | none | A value was empty or out of range; no request was sent. It is also a `ValueError`. |

## Retries

The client does not retry by default. To retry HTTP 429 responses, pass a `RetryPolicy`:

```python
from fraudnova import Client, RetryPolicy

client = Client("fn_your_api_key", retry=RetryPolicy(max_attempts=3))
```

`max_attempts` counts the first attempt, so `3` means up to two retries. Only 429 is retried; every other error is raised right away. The wait is the `Retry-After` header when the response has one, otherwise a short schedule for the concurrency limit and a longer one for the rate limit. When the attempts run out, the `RateLimitError` is raised. A `Retry-After` longer than `max_retry_after` (60 seconds by default) is not waited for; the `RateLimitError` is raised right away. Batch requests are safe to retry, because a 429 is returned before any item is checked.

## Bring your own HTTP client

Inject your own `httpx.Client`. Timeouts, proxies and TLS settings belong to the HTTP client, so set them there:

```python
import httpx
from fraudnova import Client

http = httpx.Client(timeout=5.0, proxy="http://proxy.internal:3128")
client = Client("fn_your_api_key", http_client=http)
```

Without an injected client, the SDK creates its own `httpx.Client` with a 30 second timeout (change it with `Client(..., timeout=10.0)`).

Use the client as a context manager, or call `close()`, to release connections when you are done. `close()` only closes an `httpx.Client` the SDK created; one you inject stays yours to close.

```python
with Client("fn_your_api_key") as client:
    client.check_email("someone@example.com")
```

## Testing

Inject an `httpx.Client` backed by `httpx.MockTransport`, so your tests send no real request:

```python
import httpx
from fraudnova import Client


def handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "success": True,
            "data": {"fraud_score": 12, "proxy": False},
            "credits_remaining": 99,
        },
    )


http = httpx.Client(transport=httpx.MockTransport(handler))
client = Client("fn_test", http_client=http)

assert client.check_ip("8.8.8.8").fraud_score == 12
```

## Credits and limits

One check costs one credit, whichever type it is. Failed checks are refunded. You get free trial credits when you verify your email address, and you buy more as credit packs, with no subscription. A batch costs one credit per successful item.

The API limits requests per minute for each key and checks in flight for each account. The current limits are in the [API documentation](https://fraudnova.com/docs).

## Resources

* [FraudNova API documentation](https://fraudnova.com/docs)
* [Examples repository](https://github.com/dahleedam/fraudnova-examples)
* [Status](https://fraudnova.com/status)
* [Changelog](https://fraudnova.com/changelog)
* Support: [support@fraudnova.com](mailto:support@fraudnova.com)

## Licence

Released under the MIT license. See [LICENSE](LICENSE).

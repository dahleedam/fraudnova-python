# FraudNova Python SDK — design (2026-11-06)

## Intent

Ship the official Python client for the FraudNova API as the PyPI package `fraudnova`, so a Python
developer can score an IP, email address or phone number in four lines without writing HTTP code or
re-implementing the error envelope. It mirrors the PHP SDK (`fraudnova/fraudnova-php`, shipped
2026-11-06) in public shape and naming wherever Python idioms allow, so the two READMEs and the
`/docs` tabs read as one family.

Sibling projects to stay consistent with: the PHP SDK (`/Users/dahleedam/Herd/fraudnova-php`, whose
design spec `docs/superpowers/specs/2026-11-06-php-sdk-design.md` is the reference for API facts),
the n8n community node (`n8n-nodes-fraudnova`) and the examples repository
(`dahleedam/fraudnova-examples`, `examples/python/*.py`).

## Goals

- `pip install fraudnova` then `Client("fn_…").check_ip("8.8.8.8").fraud_score`.
- Every public endpoint wrapped: `GET /check`, `/check/email`, `/check/phone`, the three batch
  endpoints, `GET /balance`, public `GET /my-ip`.
- Typed result dataclasses with `flagged()` / `flag_reasons()` mirroring the n8n node and the PHP SDK.
- Every API error status mapped to a typed exception; opt-in retry on 429 honouring `Retry-After`.
- Batch methods accept any number of items and chunk by 100 (the brief asks for this; the PHP SDK
  throws above 100 instead — see "Batch").
- Python 3.9 to 3.13, one runtime dependency (`httpx`), pytest with a mocked transport, ruff and
  mypy strict clean, CI on 3.9–3.13, PyPI Trusted Publishing on a `v*` tag.
- Repo ready for the owner to push to `github.com/dahleedam/fraudnova-python` and tag `v1.0.0`.

## Non-goals (v1)

- No async client (`httpx.AsyncClient`) — may come in 1.1.
- No webhook signature helper (the examples repo has one).
- No caching, logging, or retries on anything but 429.
- No framework integrations (Django/Flask).

## Anti-goals

- Nothing in the package, README, docstrings, tests, this document, the changelog or commit
  messages may name the upstream scoring provider (full name or four-letter abbreviation) or
  describe pool internals, upstream credentials, credentials or quotas. A test greps the repository for the
  forbidden strings, assembled from fragments inside the test file.
- The API key must never appear in an exception message, `repr()` or log line.
- No heavy dependencies: runtime requires `httpx` only.

## Constraints

- Python ≥ 3.9 (so `typing.Optional`/`List`/`Dict` spellings, no `X | Y` at runtime, no `match`).
  CI matrix 3.9, 3.10, 3.11, 3.12, 3.13. Local toolchain: `uv` with Python 3.9.25 in `.venv`,
  Python 3.13.18 available for a second run.
- Runtime dependency: `httpx>=0.26,<1.0`. Dev: `pytest`, `mypy`, `ruff` (optional-dependency group
  `dev`).
- Build backend: hatchling, `src/` layout, version read from `src/fraudnova/_version.py`.
- Licence MIT, copyright "FraudNova" (same text as the PHP SDK).
- Commits end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. The owner pushes.

## The API being wrapped

Identical to the PHP spec's "The API being wrapped" section; the facts that matter here:

- Base URL `https://fraudnova.com/api/v1`, header `Authorization: Bearer fn_…`, JSON everywhere.
- Single checks: `GET /check?ip=…` (+ `strictness` 0–3, `mobile` true/false, `user_agent` ≤512,
  `user_language` ≤32), `GET /check/email?email=…`, `GET /check/phone?phone=…&country=XX`.
  Success body `{success: true, data: {…}, credits_remaining: int}`.
- Batches: `POST /check/batch` `{ips: […≤100], strictness?, mobile?, user_agent?, user_language?}`,
  `POST /check/email/batch` `{emails: […]}`, `POST /check/phone/batch` `{phones: […], country?}`.
  Success body `{success: true, results: [{ip|email|phone, success, data?, error?}], credits_remaining}`.
  Per-item `error`: `invalid_ip` / `invalid_email` / `invalid_phone`, `insufficient_credits`,
  `upstream_failed`. Always HTTP 200 on a valid envelope; 402 only when the balance was zero at the
  start; 422 on a bad envelope.
- `GET /balance` → `{success: true, credits_remaining}`; `GET /my-ip` (no auth) → `{success: true, ip}`.
- Error envelope `{success: false, message: "…"}`: 401 token missing/invalid, 402 "Insufficient
  credits.", 403 "Account suspended.", 422 first validation message, 429 "Rate limit exceeded. Try
  again shortly." (per-key) or "Too many concurrent requests for this account. Please retry."
  (per-account cap), 503 "Upstream lookup failed." (credit refunded). **Both 429s now send
  `Retry-After`** (added 2026-11-06; the concurrency cap sends `Retry-After: 1`).
- Cloudflare fronts the API: a non-JSON HTML body with 5xx (or a challenge page with 4xx) is possible.
- Email results' `first_seen` and `domain_age` are `{human, timestamp, iso}` objects.
- Result fields per type: exactly the lists in the PHP spec (IP `fraud_score`, `proxy`, `vpn`, `tor`,
  `active_vpn`, `active_tor`, `recent_abuse`, `bot_status`, `country_code`, `region`, `city`, `ISP`,
  `organization`, `ASN`, `operating_system`, `browser`, `device_brand`, `device_model`; email
  `valid`, `disposable`, `catch_all`, `generic`, `common`, `dns_valid`, `honeypot`,
  `frequent_complainer`, `suspect`, `recent_abuse`, `leaked`, `risky_tld`, `spf_record`,
  `dmarc_record`, `fraud_score`, `smtp_score`, `overall_score`, `deliverability`, `spam_trap_score`,
  `result_type`, `sanitized_email`, `first_seen`, `domain_age`; phone `valid`, `recent_abuse`, `VOIP`,
  `prepaid`, `risky`, `active`, `do_not_call`, `leaked`, `spammer`, `fraud_score`, `dialing_code`,
  `carrier`, `line_type`, `country`, `region`, `city`, `timezone`, `zip_code`, `active_status`,
  `formatted`, `local_format`). Any field may be absent; parsing never raises on a mistyped field
  (lenient coercion, raw value kept in `raw`).

## Package shape

```
fraudnova-python/
  pyproject.toml            name "fraudnova", hatchling, src layout, optional-dependencies dev
  src/fraudnova/
    __init__.py             public re-exports + __all__
    _version.py             __version__ = "1.0.0"
    py.typed
    client.py               Client
    exceptions.py           the exception hierarchy
    retry.py                RetryPolicy, parse_retry_after()
    results.py              DateInfo, IpResult, EmailResult, PhoneResult, BatchItem, BatchResult, coercion helpers
    _transport.py           Transport (internal): builds/sends requests, decodes, maps errors, applies RetryPolicy
  tests/                    pytest; conftest.py with a MockTransport-backed client factory
  .github/workflows/ci.yml, release.yml
  README.md, CHANGELOG.md, LICENSE, .gitignore, .editorconfig
  docs/RELEASING.md, docs/superpowers/specs|plans/…
```

## Public API

```python
from fraudnova import Client, RetryPolicy

client = Client("fn_your_key")  # httpx.Client created internally, 30 s timeout
client = Client(
    "fn_your_key",
    base_url="https://fraudnova.com/api/v1",
    timeout=10.0,
    retry=RetryPolicy(max_attempts=3),
    http_client=my_httpx_client,
)

ip = client.check_ip("8.8.8.8")  # IpResult
ip = client.check_ip("8.8.8.8", strictness=3, mobile=True, user_agent=ua, user_language="en-US")
email = client.check_email("user@example.com")  # EmailResult
phone = client.check_phone("18176791808", country="US")  # PhoneResult

batch = client.check_ips(["8.8.8.8", "1.1.1.1"], strictness=2)  # BatchResult, chunked by 100
batch = client.check_emails([...])
batch = client.check_phones([...], country="US")

credits = client.balance()  # int
my_ip = client.my_ip()  # str

with Client("fn_…") as client:
    ...  # closes the httpx client it created
```

Constants: `fraudnova.BATCH_MAX = 100`, `fraudnova.DEFAULT_BASE_URL`, `fraudnova.__version__`.

Behaviour:

- `api_key` is stripped; empty raises `InvalidArgumentError`. `base_url` must start with `http://`
  or `https://` (case-insensitive) else `InvalidArgumentError`; a trailing slash is tolerated.
- Subjects are stripped; an empty subject raises `InvalidArgumentError` before any request.
- `strictness` outside 0–3 raises `InvalidArgumentError`; only non-`None` options are sent. In the
  GET query `mobile` is sent as the literal `true`/`false`; in a batch JSON body it is a JSON boolean.
- `country` is stripped and upper-cased; empty/`None` is not sent.
- **Batch:** `check_ips`/`check_emails`/`check_phones` take any sequence of `str` or `None`. An empty
  sequence raises `InvalidArgumentError`; any item that is neither `str` nor `None` raises
  `InvalidArgumentError` naming its index. Items are stripped (`None` and `""` are sent as-is; the API
  answers them per item). The list is split into chunks of `BATCH_MAX` and one POST is sent per
  chunk, in order; the returned `BatchResult.items` is the concatenation in input order and
  `credits_remaining` is the last response's value. An exception on a later chunk propagates after
  earlier chunks were already billed — the README says so and tells users who need per-chunk control
  to slice the list themselves.
- `my_ip()` sends no `Authorization` header. Every other call sends it.
- Headers on every request: `Accept: application/json`, `User-Agent: fraudnova-python/<version>
  python/<X.Y.Z>`; `Content-Type: application/json` on POST (httpx sets it for `json=`).
- `timeout` applies only to the client the SDK creates; an injected `http_client` keeps its own
  timeout/proxy/TLS settings. `close()` closes only a client the SDK created. `repr(client)` shows
  the key masked (`fn_…` + last four characters, or just `fn_…` when the key is ≤ 12 characters).

### Results

`IpResult`, `EmailResult`, `PhoneResult` are frozen dataclasses built via
`from_dict(data: Mapping[str, Any], credits_remaining: Optional[int] = None)`. Each exposes:

- snake_case fields for every documented API field (`fraud_score: int` — defaults to 0 when missing or
  mistyped; everything else `Optional`). API names that are not snake_case map as `ISP` → `isp`,
  `ASN` → `asn`, `VOIP` → `voip`. Email `first_seen` / `domain_age` are `Optional[DateInfo]`.
- `credits_remaining: Optional[int]` (`None` on batch items; set on single checks).
- `raw: Dict[str, Any]` — the `data` object exactly as returned (unknown fields included), excluded
  from `repr`; `to_dict()` returns a shallow copy of it.
- `flag_reasons(risk_threshold: int = 75, flag_on: Optional[Sequence[str]] = None) -> List[str]`
  and `flagged(...) -> bool`: `fraud_score >= risk_threshold` adds `"fraud_score"`; each name in
  `flag_on` whose raw value `is True` adds that name. Defaults (`DEFAULT_FLAG_ON` class attribute, a
  tuple of raw API field names): IP `("proxy", "vpn", "tor")`, email `("disposable",)`, phone
  `("VOIP", "risky")`.

`DateInfo` (frozen dataclass): `human: Optional[str]`, `timestamp: Optional[int]`, `iso: Optional[str]`;
`DateInfo.from_value(v)` returns `None` for `None`/unsupported types, maps a dict's three keys with
lenient coercion, and wraps a bare string as `DateInfo(human=v, timestamp=None, iso=None)`.

Coercion (module-private helpers in `results.py`): `_bool` accepts only `bool`; `_int` accepts `int`
(not `bool`), whole-number or decimal strings, and finite floats (rounded half away from zero);
`_str` accepts only `str`. Anything else → `None`.

`BatchResult` (frozen dataclass): `items: List[BatchItem]`, `credits_remaining: int`; `successful()`,
`failed()`, `has_failures()`, `__len__`, `__iter__`, `__getitem__`. `BatchItem`: `subject: str`,
`success: bool`, `result: Optional[Union[IpResult, EmailResult, PhoneResult]]`, `error: Optional[str]`,
and `is_invalid()`, `is_insufficient_credits()`, `is_upstream_failed()`.
`BatchResult.from_dict(envelope, kind: Literal["ip", "email", "phone"])` parses one response.

### Exceptions (`fraudnova.exceptions`)

```
FraudNovaError(Exception)
├── InvalidArgumentError(FraudNovaError, ValueError)      client-side input problems, no request sent
├── TransportError(FraudNovaError)                         httpx failed (timeout, DNS, TLS); __cause__ = original
└── ApiError(FraudNovaError)                               status_code: int, api_message: str, body: Dict[str, Any]
    ├── AuthenticationError        401 (envelope only)
    ├── InsufficientCreditsError   402 (envelope only)
    ├── AccountSuspendedError      403 (envelope only)
    ├── ValidationError            422 (envelope only)
    ├── RateLimitError             429 always; retry_after: Optional[int]; is_concurrency_limit (property)
    ├── UpstreamError              502/503/504; credit_refunded: bool (True only for a 503 with the envelope)
    └── UnexpectedResponseError    a 2xx whose body is not the success envelope
```

`str(ApiError)` is `"FraudNova API error (HTTP 429): Rate limit exceeded. Try again shortly."`;
for a non-JSON body it is `"FraudNova API error (HTTP 503): non-JSON response"`; `UpstreamError`
appends `" The credit for this check was refunded."` when `credit_refunded`. `api_message` is the
envelope's `message` (or `error`) string when non-empty, else the raw body stripped and truncated
to 200 characters, else `"HTTP <status>"`. "Envelope" means the decoded JSON object has a `success`
or `message` key — a Cloudflare JSON/HTML page with 401/402/403/422 is a plain `ApiError`.
`RateLimitError.is_concurrency_limit` is `"Too many concurrent requests" in api_message`.

### Retry (opt-in)

`RetryPolicy` (frozen dataclass): `max_attempts: int = 3` (total attempts including the first),
`concurrency_delays: Sequence[float] = (1, 2, 4)`, `rate_limit_delays: Sequence[float] = (5, 15, 40)`,
`honour_retry_after: bool = True`, `max_retry_after: float = 60`, `sleeper: Callable[[float], None]
= time.sleep`. `max_attempts < 1` or `max_retry_after < 0` raises `InvalidArgumentError`.
`delay_for(error: RateLimitError, attempt: int) -> Optional[float]` (attempt is 1-based, the one
that just failed): `None` when `attempt >= max_attempts`; else the `Retry-After` value when honoured
and present (`None` — stop — when it exceeds `max_retry_after`; `0` is honoured); else the schedule
entry `[attempt - 1]` for concurrency vs rate-limit, `None` when the schedule runs out.
Only 429 is retried; `balance()`/`my_ip()`/batches use the same policy.
`parse_retry_after(value: Optional[str], now: Optional[datetime] = None) -> Optional[int]`
accepts delta-seconds or an HTTP-date (`email.utils.parsedate_to_datetime`), clamped at 0.

### Transport (internal)

`Transport(api_key, base_url, timeout, retry, http_client)`; `get(path, params=None,
authenticated=True) -> Dict[str, Any]`, `post(path, json) -> Dict[str, Any]`, `close()`,
`owns_client: bool`. The 2xx body must decode to a JSON object with `success is True`; otherwise
`UnexpectedResponseError`. Callers (`Client`) check for `data` / `results` / `credits_remaining` /
`ip` and raise `UnexpectedResponseError(status, "Missing data")` etc. when absent.

## Quality bar

- pytest with `httpx.MockTransport`; no test performs network I/O. `tests/conftest.py` exposes a
  `make_client(*responses)` fixture that returns `(client, sent_requests)`.
- Coverage expectations: request building per endpoint (method, path, query encoding, JSON body,
  headers, no auth on `/my-ip`), chunking (250 items → 3 POSTs of 100/100/50, items concatenated,
  credits from the last), result parsing incl. missing/mistyped fields and the `DateInfo` shapes,
  every status → exception class (envelope vs non-envelope), `Retry-After` parsing, retry schedule
  + sleeper calls + give-up + `max_retry_after`, batch parsing incl. all error codes and unknown
  codes, flagged defaults per type and custom thresholds, key masking in `repr`, close semantics,
  leak guard, `__version__` ↔ CHANGELOG, README method names exist on `Client`.
- `ruff check .` and `ruff format --check .` clean; `mypy` strict on `src` and `tests` clean on 3.9.
- CI: matrix 3.9–3.13: install `.[dev]`, ruff check + format check, mypy, pytest; plus a build job
  (`python -m build`, `twine check dist/*`). Release workflow on `v*.*.*` tags: build → publish with
  `pypa/gh-action-pypi-publish` under environment `pypi` with `id-token: write` (Trusted Publishing,
  no API token) → GitHub release with generated notes.

## README outline

Title + one-paragraph pitch (same wording family as the PHP README), badges (CI, PyPI version,
Python versions, licence), Requirements, Installation (`pip install fraudnova`), Quickstart (4 lines),
Checking IPs/emails/phones (keyword options), Batch checks (chunking, per-item errors table),
Results (fields, `to_dict()`, `credits_remaining`), The `flagged()` helper, Balance and your IP,
Errors (exception table), Retries, Bring your own HTTP client (`httpx.Client` with proxies/timeouts;
closing), Testing (inject `httpx.MockTransport`), Credits and limits, Resources, Licence.

## Release & hand-over

Single `main` branch, conventional-style commits, Keep-a-Changelog `CHANGELOG.md` with a `1.0.0`
section dated 2026-11-06. `docs/RELEASING.md` carries the owner's numbered steps: create the GitHub
repo, push, configure the PyPI trusted publisher (PyPI project `fraudnova`, owner `dahleedam`,
repository `fraudnova-python`, workflow `release.yml`, environment `pypi`) as a *pending* publisher
before the first release, create the `pypi` environment on GitHub, tag `v1.0.0`, verify
`pip install fraudnova` in an empty venv.

Main-app follow-ups (done in the same session, separate repos): `/docs#python-sdk` section + a
"Python SDK" tab on all six code-sample groups, changelog seeder entry `python-sdk` (Improved,
2026-11-07), `docs/DEPLOY.md` note, examples README link.

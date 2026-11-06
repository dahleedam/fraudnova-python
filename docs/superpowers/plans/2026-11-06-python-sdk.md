# FraudNova Python SDK Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `fraudnova` PyPI package (official Python client, v1.0.0) and wire it into the FraudNova app docs, changelog and examples repo, mirroring the PHP SDK that shipped on 2026-11-06.

**Architecture:** A thin `Client` delegates HTTP to an internal `Transport` (httpx) that decodes the JSON envelope, maps error statuses to typed exceptions and applies an opt-in `RetryPolicy`; results are frozen dataclasses with lenient coercion and `flagged()` helpers. Tasks 1–6 build the package in `/Users/dahleedam/Herd/fraudnova-python`; Task 7 edits the Laravel app worktree; Task 8 edits the examples repo.

**Tech Stack:** Python 3.9–3.13, httpx, hatchling, pytest, ruff, mypy (strict); Laravel 13 Blade + PHPUnit for Task 7.

**Spec:** `docs/superpowers/specs/2026-11-06-python-sdk-design.md` (this repo). API facts also in the PHP spec at `/Users/dahleedam/Herd/fraudnova-php/docs/superpowers/specs/2026-11-06-php-sdk-design.md`.

## Global Constraints

- Python ≥ 3.9 syntax everywhere (`Optional[...]`, `List[...]`, `Dict[...]`, no `X | Y` at runtime, no `match`); `from __future__ import annotations` is allowed in modules but dataclass field types must still resolve on 3.9.
- Runtime dependency: `httpx>=0.23,<1.0` only. Dev tools: `pytest`, `mypy`, `ruff`.
- Package name `fraudnova`, version `1.0.0`, `src/` layout, hatchling, `py.typed` shipped.
- `User-Agent: fraudnova-python/<version> python/<X.Y.Z>` on every request; `Authorization: Bearer <key>` on every request except `GET /my-ip`.
- Batch chunk size `BATCH_MAX = 100`; risk threshold default 75; default flag fields IP `("proxy", "vpn", "tor")`, email `("disposable",)`, phone `("VOIP", "risky")`.
- Retry defaults: `max_attempts=3`, `concurrency_delays=(1, 2, 4)`, `rate_limit_delays=(5, 15, 40)`, `honour_retry_after=True`, `max_retry_after=60`.
- No file in any of the three repos may contain the upstream provider's name, its four-letter abbreviation, the two forbidden pool-internals phrases (see the leak-guard test) (case-insensitive). The leak-guard test assembles the forbidden strings from fragments.
- The API key never appears in exception text or `repr`.
- Every commit message ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Nothing is pushed or published.
- Local commands in the SDK repo: `.venv/bin/pytest -q`, `.venv/bin/ruff check . && .venv/bin/ruff format --check .`, `.venv/bin/mypy`. In the app worktree: `php -d memory_limit=512M vendor/bin/phpunit`, `vendor/bin/phpstan analyse --memory-limit=512M`, `vendor/bin/pint --test`.

## Review Focus

1. A 429 whose body is Cloudflare HTML (no JSON) must still be a `RateLimitError` so retry works; a 401/402/403/422 HTML page must be a plain `ApiError` (never a semantic subclass) — test in Task 2 (`test_html_401_is_plain_api_error`, `test_html_429_is_rate_limit_error`).
2. `fraud_score` arriving as `87.5` or `"88"` must still flag at threshold 75; `True` must not be read as `1` by `_int` — test in Task 3 (`test_int_coercion`).
3. `check_ips` with 250 items must send exactly three POSTs (100/100/50) in order and return 250 items; an exception on chunk 2 must propagate (not be swallowed) — tests in Task 5 (`test_check_ips_chunks_by_100`, `test_batch_error_on_later_chunk_propagates`).
4. `Retry-After: 0` must be honoured as a zero-second wait, not treated as absent; a `Retry-After` of 120 with `max_retry_after=60` must stop retrying — tests in Task 2 (`test_delay_for_honours_zero_retry_after`, `test_delay_for_stops_when_retry_after_exceeds_max`).
5. A batch response item with `success: true` but a missing/non-dict `data` must yield `result=None`, `success=True` without raising — test in Task 3 (`test_batch_item_success_without_data`).

---

### Task 1: Package scaffold, metadata, leak guard

**Files:**
- Create: `pyproject.toml`, `LICENSE`, `.gitignore`, `.editorconfig`, `CHANGELOG.md`, `src/fraudnova/_version.py`, `src/fraudnova/__init__.py`, `src/fraudnova/py.typed`, `tests/__init__.py` (empty), `tests/test_leak_guard.py`, `tests/test_release_consistency.py`

**Interfaces:**
- Produces: `fraudnova.__version__ == "1.0.0"`; the repo-wide leak guard every later task must pass; `pyproject.toml` tool config (ruff target py39, line length 100, `select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`; mypy `strict = true`, `python_version = "3.9"`, `files = ["src", "tests"]`; pytest `testpaths = ["tests"]`).

- [ ] **Step 1: Write `pyproject.toml`**

`[build-system]` hatchling; `[project]` name `fraudnova`, dynamic version from `src/fraudnova/_version.py` (`[tool.hatch.version] path`), description "Official Python client for the FraudNova fraud-detection API (IP, email and phone checks)", readme `README.md`, `requires-python = ">=3.9"`, license `MIT`, authors `[{ name = "FraudNova", email = "support@fraudnova.com" }]`, keywords `fraud, fraud-detection, ip, proxy, vpn, email-validation, phone-validation, api-client`, classifiers for 3.9–3.13 + "Typing :: Typed" + "License :: OSI Approved :: MIT License", `dependencies = ["httpx>=0.23,<1.0"]`, `[project.optional-dependencies] dev = ["pytest>=7", "mypy>=1.8", "ruff>=0.5"]`, `[project.urls]` Homepage `https://fraudnova.com`, Documentation `https://fraudnova.com/docs`, Repository `https://github.com/dahleedam/fraudnova-python`, Changelog `https://github.com/dahleedam/fraudnova-python/blob/main/CHANGELOG.md`. `[tool.hatch.build.targets.wheel] packages = ["src/fraudnova"]`; sdist excludes `.github`, `docs`, `tests` not needed — include tests in sdist (default) but exclude `.venv`, `.superpowers`. Tool config as in Interfaces.

- [ ] **Step 2: Write `LICENSE` (MIT, "Copyright (c) 2026 FraudNova", same text as `/Users/dahleedam/Herd/fraudnova-php/LICENSE`), `.gitignore`** (`.venv/`, `__pycache__/`, `*.pyc`, `dist/`, `build/`, `*.egg-info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `uv.lock`, `.superpowers/`, `.DS_Store`, `.idea/`, `.vscode/`), **`.editorconfig`** (copy of the PHP SDK's, but `indent_size = 4` for `*.py` and 2 for yml/yaml/json/toml).

- [ ] **Step 3: Write `src/fraudnova/_version.py`** (`__version__ = "1.0.0"`), **`src/fraudnova/__init__.py`** (for now: `from ._version import __version__`, `__all__ = ["__version__"]`), empty **`src/fraudnova/py.typed`**, **`CHANGELOG.md`** in Keep-a-Changelog form with `## [Unreleased]` and `## [1.0.0] - 2026-11-06` (Added bullets: Client for every endpoint; typed results with `flagged()`; typed exceptions; opt-in 429 retry honouring `Retry-After`; batch helpers that chunk by 100; bring-your-own `httpx.Client`) and link references to `https://github.com/dahleedam/fraudnova-python/compare/v1.0.0...HEAD` and `.../releases/tag/v1.0.0`.

- [ ] **Step 4: Write `tests/test_leak_guard.py`**

```python
FORBIDDEN = ["".join(["IP", "Quality", "Score"]), "".join(["IP", "QS"]), "upstream " + "key", "key " + "pool"]
SKIP_DIRS = {".git", ".venv", ".superpowers", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}

def test_no_file_names_the_upstream_provider() -> None:
    # walks the repo root (parent of tests/), reads every file as UTF-8 (errors="ignore"),
    # lower-cases both sides, asserts no forbidden string appears; the failure message names the file.
```

- [ ] **Step 5: Write `tests/test_release_consistency.py`**

```python
def test_version_matches_latest_changelog_release() -> None:
    # first "## [X.Y.Z]" heading in CHANGELOG.md equals fraudnova.__version__
```

- [ ] **Step 6: Run the checks**

Run: `.venv/bin/pip install -e . --no-deps -q` (or `uv pip install --python .venv/bin/python -e . --no-deps`), then `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`
Expected: 2 passed, ruff clean, mypy "Success".

- [ ] **Step 7: Commit** — `chore: scaffold the fraudnova package` (+ Co-Authored-By line).

---

### Task 2: Exceptions and retry policy

**Files:**
- Create: `src/fraudnova/exceptions.py`, `src/fraudnova/retry.py`, `tests/test_exceptions.py`, `tests/test_retry.py`

**Interfaces:**
- Produces: the hierarchy in the spec; `ApiError.__init__(self, status_code: int, api_message: str, body: Optional[Dict[str, Any]] = None, message: Optional[str] = None)`; `RateLimitError.__init__(..., retry_after: Optional[int] = None, ...)` + property `is_concurrency_limit`; `UpstreamError.__init__(..., credit_refunded: bool = False, ...)`; classmethod `ApiError.from_response(status_code: int, text: str, retry_after: Optional[int] = None) -> "ApiError"` (does the envelope detection + subclass dispatch described in the spec; a JSON `error` key is accepted as an alternative to `message`); `RetryPolicy` (frozen dataclass, fields/defaults in Global Constraints) with `delay_for(error: RateLimitError, attempt: int) -> Optional[float]` and `sleep(seconds: float) -> None`; `parse_retry_after(value: Optional[str], now: Optional[datetime] = None) -> Optional[int]`.

- [ ] **Step 1: Write `tests/test_exceptions.py`** with: `test_every_error_is_a_fraudnova_error` (all classes subclass `FraudNovaError`; `InvalidArgumentError` also `ValueError`); `test_status_dispatch` parametrized over `(401, AuthenticationError), (402, InsufficientCreditsError), (403, AccountSuspendedError), (422, ValidationError), (429, RateLimitError), (502, UpstreamError), (503, UpstreamError), (504, UpstreamError), (500, ApiError), (418, ApiError)` using body `{"success": false, "message": "x"}`; `test_message_format` (`str(e) == "FraudNova API error (HTTP 402): Insufficient credits."`); `test_error_key_is_accepted_as_message`; `test_html_401_is_plain_api_error` (body `<html>…`, `type(e) is ApiError`, `api_message` is the stripped HTML truncated to 200 chars, `str(e)` ends with "non-JSON response"); `test_html_429_is_rate_limit_error`; `test_503_envelope_marks_credit_refunded` (`credit_refunded is True`, message ends with "The credit for this check was refunded."); `test_503_html_is_not_refunded`; `test_rate_limit_retry_after_and_concurrency` (`retry_after == 7`, `is_concurrency_limit` True for "Too many concurrent requests for this account. Please retry."); `test_empty_body_message_is_http_status` (`api_message == "HTTP 500"`).

- [ ] **Step 2: Write `tests/test_retry.py`** with: `test_parse_retry_after_delta_and_date` (`"5"` → 5, `" 12 "` → 12, an RFC 7231 date 30 s after `now` → 30, a past date → 0, `"soon"`/`""`/`None` → `None`); `test_policy_validates` (`max_attempts=0` and `max_retry_after=-1` raise `InvalidArgumentError`); `test_delay_for_uses_schedules` (concurrency error: attempts 1, 2 → 1.0, 2.0; rate-limit: 5.0, 15.0; attempt 3 with default `max_attempts=3` → `None`); `test_delay_for_honours_retry_after` (retry_after=7 → 7.0); `test_delay_for_honours_zero_retry_after` (→ 0.0); `test_delay_for_stops_when_retry_after_exceeds_max` (120 with max 60 → `None`); `test_delay_for_ignores_retry_after_when_disabled`; `test_schedule_exhaustion_returns_none` (`max_attempts=10`, `rate_limit_delays=(5,)`, attempt 2 → `None`); `test_sleep_calls_sleeper` (recorder list).

- [ ] **Step 3: Run both test files** — Expected: FAIL with ImportError.

- [ ] **Step 4: Implement `src/fraudnova/exceptions.py` and `src/fraudnova/retry.py`** per the Interfaces block and the spec's "Exceptions" and "Retry" sections. `retry.py` imports `RateLimitError` from `exceptions.py` (never the reverse); `exceptions.py` must not import `retry.py` — `from_response` takes the already-parsed header string and calls `parse_retry_after` lazily via a local import, or `parse_retry_after` lives in `retry.py` and `from_response` receives `retry_after: Optional[int]` already parsed. **Ruling: `from_response(status_code, text, retry_after: Optional[int])` takes the parsed integer; the transport (Task 4) parses the header with `parse_retry_after`.** Masking helper `mask_api_key(api_key: str) -> str` lives in `exceptions.py` too (`"fn_…" + key[-4:]` when `len(key) > 12`, else `"fn_…"`).

- [ ] **Step 5: Run** `.venv/bin/pytest -q tests/test_exceptions.py tests/test_retry.py && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy` — Expected: all pass, clean.

- [ ] **Step 6: Commit** — `feat: typed exceptions for every API status and an opt-in 429 retry policy`.

---

### Task 3: Result dataclasses

**Files:**
- Create: `src/fraudnova/results.py`, `tests/test_results.py`

**Interfaces:**
- Produces: `DateInfo`, `IpResult`, `EmailResult`, `PhoneResult` (each `from_dict(data: Mapping[str, Any], credits_remaining: Optional[int] = None)`, `to_dict() -> Dict[str, Any]`, `flag_reasons(risk_threshold: int = 75, flag_on: Optional[Sequence[str]] = None) -> List[str]`, `flagged(...) -> bool`, class attr `DEFAULT_FLAG_ON: Tuple[str, ...]`, field `raw: Dict[str, Any]` with `repr=False`, `credits_remaining: Optional[int]`); `BatchItem`, `BatchResult.from_dict(envelope: Mapping[str, Any], kind: Literal["ip", "email", "phone"]) -> "BatchResult"`; module helpers `_bool`, `_int`, `_str`, `_coerce_int` exposed for tests via `from fraudnova.results import _int` (ruff `PLC2701` is not selected, so private imports in tests are fine); `Result = Union[IpResult, EmailResult, PhoneResult]` type alias.

- [ ] **Step 1: Write `tests/test_results.py`** with: `test_int_coercion` (`_int(5)==5`, `_int("88")==88`, `_int(87.5)==88`, `_int("87.5")==88`, `_int(True) is None`, `_int("abc") is None`, `_int(float("nan")) is None`, `_int(None) is None`); `test_ip_result_maps_every_field` (full fixture with `ISP`/`ASN` → `isp`/`asn`, `credits_remaining=42`, `raw` is the input, `to_dict()` is a copy); `test_ip_result_missing_fields_default_to_none_and_zero_score`; `test_mistyped_field_is_none_but_kept_in_raw` (`"proxy": "yes"` → `proxy is None`, `raw["proxy"] == "yes"`); `test_fractional_score_still_flags` (`"fraud_score": 87.5` → `flagged()` True, reasons `["fraud_score"]`); `test_flag_defaults_per_type` (IP proxy True → `["proxy"]`; email disposable → `["disposable"]`; phone `VOIP` → `["VOIP"]`; a `"vpn": 1` is not `True` → not flagged); `test_custom_threshold_and_flag_on`; `test_email_date_fields` (dict `{"human": "3 years ago", "timestamp": 1600000000, "iso": "2020-09-13T12:26:40+00:00"}` → `DateInfo` with all three; bare string `"2020-09-13"` → `DateInfo(human="2020-09-13", timestamp=None, iso=None)`; `None`/`7` → `None`); `test_phone_result_maps_voip_and_strings`; `test_batch_result_parses_items_and_helpers` (three items: success with data, `invalid_ip`, `insufficient_credits`, plus an `upstream_failed` and an unknown `"weird"` code; `len`, iteration, `[0]`, `successful()`, `failed()`, `has_failures()`, `is_invalid()` etc.; `credits_remaining`); `test_batch_item_success_without_data` (`{"email": "a@b.c", "success": true}` → `result is None`, `success is True`); `test_batch_result_tolerates_garbage` (`results` missing → empty; a non-dict item skipped; `credits_remaining` missing → 0).

- [ ] **Step 2: Run** — Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `src/fraudnova/results.py`**: frozen dataclasses (`@dataclass(frozen=True)`), the shared flag logic in a small mixin base `_FlaggableResult` providing `flag_reasons`/`flagged`/`to_dict` from `self.raw` and `DEFAULT_FLAG_ON`; `from_dict` builds every field through the coercers. Field lists exactly as the spec's "Result fields" (snake_case; `ISP`→`isp`, `ASN`→`asn`, `VOIP`→`voip`).

- [ ] **Step 4: Run** `.venv/bin/pytest -q tests/test_results.py && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy` — Expected: pass, clean.

- [ ] **Step 5: Commit** — `feat: typed IP, email, phone and batch results with lenient parsing and flagged()`.

---

### Task 4: Transport

**Files:**
- Create: `src/fraudnova/_transport.py`, `tests/conftest.py`, `tests/test_transport.py`

**Interfaces:**
- Consumes: Task 2 (`ApiError.from_response`, `RateLimitError`, `TransportError`, `UnexpectedResponseError`, `RetryPolicy`, `parse_retry_after`), `fraudnova.__version__`.
- Produces: `Transport.__init__(self, api_key: str, base_url: str, timeout: float, retry: Optional[RetryPolicy], http_client: Optional[httpx.Client])`; `get(self, path: str, params: Optional[Mapping[str, Union[str, int]]] = None, authenticated: bool = True) -> Dict[str, Any]`; `post(self, path: str, json: Mapping[str, Any]) -> Dict[str, Any]`; `close()`; `owns_client: bool`; `base_url` (trailing slash stripped). `tests/conftest.py` fixture `make_http_client` → callable `(*responses: httpx.Response) -> Tuple[Transport-or-Client, List[httpx.Request]]` — **Ruling: conftest builds `httpx.Client(transport=httpx.MockTransport(handler))` where the handler pops queued responses (raising `AssertionError("no more responses")` when empty) and appends each request to a list; it returns the raw `httpx.Client` and the list, so both Task 4 and Task 5 wrap it as they need** (`make_http_client(*responses)`), plus helper `json_response(status: int, body: Any, headers: Optional[Dict[str, str]] = None) -> httpx.Response`.

- [ ] **Step 1: Write `tests/test_transport.py`** with: `test_get_builds_url_headers_and_query` (base `https://fraudnova.com/api/v1/` with trailing slash; `get("/check", {"ip": "8.8.8.8", "mobile": "true"})` → request URL `https://fraudnova.com/api/v1/check?ip=8.8.8.8&mobile=true`, headers `Accept: application/json`, `Authorization: Bearer fn_test_key_1234567890`, `User-Agent` startswith `fraudnova-python/1.0.0 python/`); `test_unauthenticated_get_sends_no_authorization`; `test_post_sends_json_body` (`Content-Type: application/json`, decoded body equals input); `test_non_2xx_maps_to_api_error` (402 envelope → `InsufficientCreditsError`; 429 with `Retry-After: 3` → `RateLimitError.retry_after == 3`); `test_2xx_without_success_true_is_unexpected` (`{"success": false}` and `"not json"` and `[]` → `UnexpectedResponseError` with `status_code == 200`); `test_transport_error_wraps_httpx` (handler raises `httpx.ConnectTimeout` → `TransportError`, `__cause__` is the httpx error, message does not contain the key); `test_retry_on_429_then_success` (policy with recording sleeper, responses 429(concurrency) → 429(rate limit, `Retry-After: 2`) → 200: 3 requests sent, sleeper got `[1.0, 2.0]`); `test_retry_gives_up_after_max_attempts` (`max_attempts=2`, two 429s → raises `RateLimitError`, 2 requests); `test_no_retry_without_policy` (one 429 → raises, 1 request); `test_only_429_is_retried` (503 with policy → `UpstreamError`, 1 request); `test_close_only_closes_owned_client` (injected client stays open; owned client is closed — construct a `Transport` with `http_client=None` but monkeypatch `httpx.Client` to the mock-backed instance, or assert `owns_client` and that `.is_closed` flips).

- [ ] **Step 2: Run** — Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `src/fraudnova/_transport.py`**: build the default `httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0))` lazily on first request when none injected; `send` loop identical to the PHP `Transport::send` (attempt counter, `delay_for`, `sleep`); errors caught: `(httpx.HTTPError, httpx.InvalidURL, httpx.StreamError)` → `TransportError(f"FraudNova request failed: {exc}")` chained; decode via `response.json()` inside try/except `ValueError`; non-2xx → `ApiError.from_response(status, response.text, parse_retry_after(response.headers.get("Retry-After")))`.

- [ ] **Step 4: Run** `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy` — Expected: pass, clean.

- [ ] **Step 5: Commit** — `feat: httpx transport with envelope decoding, error mapping and 429 retry`.

---

### Task 5: Client and public exports

**Files:**
- Create: `src/fraudnova/client.py`, `tests/test_client.py`
- Modify: `src/fraudnova/__init__.py`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `Client` exactly as the spec's "Public API" (signatures: `__init__(self, api_key: str, *, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0, retry: Optional[RetryPolicy] = None, http_client: Optional[httpx.Client] = None)`; `check_ip(self, ip: str, *, strictness: Optional[int] = None, mobile: Optional[bool] = None, user_agent: Optional[str] = None, user_language: Optional[str] = None) -> IpResult`; `check_email(self, email: str) -> EmailResult`; `check_phone(self, phone: str, country: Optional[str] = None) -> PhoneResult`; `check_ips(self, ips: Sequence[Optional[str]], *, strictness=None, mobile=None, user_agent=None, user_language=None) -> BatchResult`; `check_emails(self, emails: Sequence[Optional[str]]) -> BatchResult`; `check_phones(self, phones: Sequence[Optional[str]], country: Optional[str] = None) -> BatchResult`; `balance(self) -> int`; `my_ip(self) -> str`; `close()`, `__enter__`/`__exit__`, `__repr__`). Module constants `DEFAULT_BASE_URL = "https://fraudnova.com/api/v1"`, `BATCH_MAX = 100` in `client.py`. `fraudnova/__init__.py` re-exports `Client`, `RetryPolicy`, `DEFAULT_BASE_URL`, `BATCH_MAX`, all result classes incl. `DateInfo`, `BatchItem`, `BatchResult`, every exception class, `__version__`, with `__all__`.

- [ ] **Step 1: Write `tests/test_client.py`** with: `test_rejects_empty_key_and_bad_base_url`; `test_repr_masks_key` (`"fn_…7890" in repr(c)` and the full key not in it; a 10-char key → `fn_…` only); `test_check_ip_sends_query_and_parses` (strictness 2, mobile True, user_agent, user_language → query has `strictness=2&mobile=true&user_agent=…&user_language=en-US`; result `IpResult` with `credits_remaining`); `test_check_ip_omits_unset_options` (query is exactly `ip=8.8.8.8`); `test_check_ip_rejects_bad_strictness_and_empty_ip` (no request sent); `test_check_email_and_phone` (phone with `country=" us "` → `country=US`; without country → no `country` param; path `/check/phone`); `test_check_ips_chunks_by_100` (250 subjects, three queued 200 responses echoing each chunk; three POSTs to `/check/batch` with bodies of 100/100/50 and `strictness: 2`, `mobile: true` as JSON booleans; 250 items in order; `credits_remaining` from the last response); `test_check_emails_and_phones_bodies` (`{"emails": [...]}`, `{"phones": [...], "country": "US"}`); `test_batch_rejects_empty_and_non_string_items` (`[]` and `["a", 5]` raise `InvalidArgumentError`, message of the latter mentions index 1; `[" a ", None, ""]` is sent as `["a", None, ""]`); `test_batch_error_on_later_chunk_propagates` (101 items, responses 200 then 402 → `InsufficientCreditsError`, 2 requests); `test_balance_and_my_ip` (`balance()` → 123 from `{"success": true, "credits_remaining": 123}`; `my_ip()` → `"203.0.113.9"`, request has no `Authorization`); `test_missing_data_is_unexpected_response` (`{"success": true}` on `/check` → `UnexpectedResponseError`, `api_message == "Missing data"`; same for `results`, `credits_remaining`, `ip`); `test_context_manager_closes_owned_client`; `test_public_exports` (`fraudnova.__all__` contains every name in the Interfaces block and each resolves).

- [ ] **Step 2: Run** — Expected: FAIL with ImportError.

- [ ] **Step 3: Implement `src/fraudnova/client.py` and update `src/fraudnova/__init__.py`**. Query values: `mobile` → `"true"`/`"false"`; in JSON bodies booleans stay booleans. Chunking: `range(0, len(items), BATCH_MAX)`.

- [ ] **Step 4: Run the full checks** `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy` — Expected: pass, clean.

- [ ] **Step 5: Commit** — `feat: fraudnova.Client with single, chunked batch, balance and my-ip calls`.

---

### Task 6: README, release docs, CI and publish workflows

**Files:**
- Create: `README.md`, `docs/RELEASING.md`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `tests/test_readme.py`

**Interfaces:**
- Consumes: the public API of Task 5 (every method name and keyword shown in the README must exist).

- [ ] **Step 1: Write `tests/test_readme.py`**: `test_readme_only_calls_methods_that_exist` (regex `client\.(\w+)\(` over README.md → every name is an attribute of `fraudnova.Client`); `test_readme_mentions_install_and_every_method` (contains `pip install fraudnova`, and each of `check_ip`, `check_email`, `check_phone`, `check_ips`, `check_emails`, `check_phones`, `balance`, `my_ip`, `flagged`, `RetryPolicy`).

- [ ] **Step 2: Write `README.md`** following the spec's "README outline", mirroring the PHP README's tone and section order with Python code (badges: CI `https://github.com/dahleedam/fraudnova-python/actions/workflows/ci.yml/badge.svg`, PyPI `https://img.shields.io/pypi/v/fraudnova`, Python versions `https://img.shields.io/pypi/pyversions/fraudnova`, licence). The Batch section states the chunking rule and the later-chunk-exception caveat verbatim from the spec; the Errors table lists every exception with status and when; the "Bring your own HTTP client" section shows `httpx.Client(timeout=5.0, proxy=...)` injection and notes `close()`; the Testing section shows `httpx.MockTransport`. `user_language` example sends only the first Accept-Language tag.

- [ ] **Step 3: Write `docs/RELEASING.md`**: numbered first-release steps — (1) create the empty public repo `dahleedam/fraudnova-python`; (2) `git remote add origin git@github.com:dahleedam/fraudnova-python.git && git push -u origin main`; (3) wait for CI green on 3.9–3.13; (4) on PyPI → Account settings → Publishing → "Add a new pending publisher": PyPI project name `fraudnova`, owner `dahleedam`, repository `fraudnova-python`, workflow `release.yml`, environment `pypi`; (5) on GitHub → Settings → Environments → create `pypi` (optionally restrict to tags `v*`); (6) `git tag v1.0.0 && git push origin v1.0.0`; (7) verify `python -m venv /tmp/fn && /tmp/fn/bin/pip install fraudnova && /tmp/fn/bin/python -c "import fraudnova; print(fraudnova.__version__)"`; patch/minor release steps (bump `_version.py`, move Unreleased into a dated section, tag); the Rules section (leak guard, version↔changelog test).

- [ ] **Step 4: Write `.github/workflows/ci.yml`** (on PR + push to main; concurrency group cancel-in-progress; job `test` matrix `python-version: ['3.9', '3.10', '3.11', '3.12', '3.13']`, `actions/checkout@v4`, `actions/setup-python@v5` with `cache: pip`, `pip install -e ".[dev]"`, `ruff check .`, `ruff format --check .`, `mypy`, `pytest -q`; job `build` on 3.12: `pip install build twine`, `python -m build`, `twine check dist/*`) and **`.github/workflows/release.yml`** (on `push: tags: ['v*.*.*']`; job `build`: setup-python 3.12, `pip install build`, `python -m build`, `actions/upload-artifact@v4` name `dist`; job `publish` needs build, `environment: pypi`, `permissions: id-token: write`, `actions/download-artifact@v4` to `dist/`, `pypa/gh-action-pypi-publish@release/v1`; job `github-release` needs publish, `permissions: contents: write`, `softprops/action-gh-release@v2` with `generate_release_notes: true` and `files: dist/*`).

- [ ] **Step 5: Run** `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy`, then a build smoke test: `uv build --python .venv/bin/python` (or `.venv/bin/pip install build && .venv/bin/python -m build`) → `dist/fraudnova-1.0.0-py3-none-any.whl` and `.tar.gz` exist; `unzip -l dist/*.whl | grep py.typed` shows the marker; then `rm -rf dist`. Expected: all pass.

- [ ] **Step 6: Commit** — `docs: README, changelog, release guide, CI and PyPI trusted-publishing workflows`.

---

### Task 7: App wiring (Laravel worktree)

**Files (all under `/Users/dahleedam/Herd/fraudnova/.claude/worktrees/friendly-wu-6cc2dc`):**
- Modify: `resources/views/docs.blade.php` (six sample arrays + new section after `#php-sdk` + the "OpenAPI & SDKs" paragraph), `tests/Feature/DocsPageTest.php`, `database/seeders/ChangelogSeeder.php`, `tests/Feature/ChangelogSeederTest.php`, `docs/DEPLOY.md`

**Interfaces:**
- Consumes: the Python API of Task 5 (method names and keyword options in the samples must match).

- [ ] **Step 1: Add `test_docs_mention_the_python_sdk` to `tests/Feature/DocsPageTest.php`** right after `test_docs_mention_the_php_sdk`, asserting `id="python-sdk"` (raw), `pip install fraudnova`, `https://github.com/dahleedam/fraudnova-python`, `https://pypi.org/project/fraudnova/`, `Python SDK`, `client.check_ip(` (raw) and `client.check_phones(` (raw). In `tests/Feature/ChangelogSeederTest.php` change both `assertSame(20, …)` to `21` (the published count at the frozen 2026-11-03 clock stays 16).

- [ ] **Step 2: Run** `php -d memory_limit=512M vendor/bin/phpunit tests/Feature/DocsPageTest.php tests/Feature/ChangelogSeederTest.php` — Expected: the new docs test and the two count assertions FAIL.

- [ ] **Step 3: Edit `resources/views/docs.blade.php`**: in each of the six sample arrays add a `'Python SDK' => <<<'EOT' … EOT,` entry directly after the `'PHP SDK'` entry:
  - check: `from fraudnova import Client` / blank / `client = Client("fn_...")` / `result = client.check_ip("8.8.8.8", strictness=2)` / `print(result.fraud_score)`
  - check-email: `result = client.check_email("user@example.com")`
  - check-phone: `result = client.check_phone("18176791808", country="US")`
  - batch: `batch = client.check_ips(["8.8.8.8", "1.1.1.1"], strictness=2)` / `for item in batch:` / `    print(item.subject, item.result.fraud_score if item.result else item.error)`
  - batch-email: `batch = client.check_emails(["user@example.com", "test@example.org"])` + same loop
  - batch-phone: `batch = client.check_phones(["18176791808", "14155552671"], country="US")` + same loop
  Add a `<section>` with `<h2 id="python-sdk">Python SDK</h2>` immediately after the PHP SDK section, same markup: a paragraph linking the GitHub repo (`https://github.com/dahleedam/fraudnova-python`) and PyPI (`https://pypi.org/project/fraudnova/`, `<code>fraudnova</code>`, Python 3.9+), "wraps every endpoint with typed results and exceptions, one dependency (httpx)"; a `<pre>` with `pip install fraudnova`; a `<pre>` with the quickstart (`from fraudnova import Client` … `if result.flagged():` … `print(result.fraud_score)`); a closing paragraph naming `check_email()`, `check_phone()`, `check_ips()`, `check_emails()`, `check_phones()` and `balance()`, "each code sample below has a "Python SDK" tab", batches "split into requests of 100 automatically", and a README link (`…/fraudnova-python#readme`) covering retries and testing. In the "OpenAPI & SDKs" section, change the PHP sentence to also mention Python: "PHP projects can use the official PHP SDK (…) and Python projects the official <a href="#python-sdk">Python SDK</a> (`fraudnova` on PyPI) instead of raw HTTP calls." Update the SEO description's "Includes curl, Python, Node.js and PHP examples." to "…PHP examples and official PHP and Python SDKs."

- [ ] **Step 4: Add the changelog entry** to `database/seeders/ChangelogSeeder.php` directly before the `php-sdk` entry (the list is newest-first): slug `python-sdk`, date `2026-11-07`, category `ChangelogCategory::Improved`, title `Official Python SDK`, body: "`pip install fraudnova` installs the official Python client (Python 3.9+). It covers IP, email and phone checks, the batch endpoints and your balance, returns typed results with a `flagged()` helper, throws a typed exception per error status, splits large batches into requests of 100 automatically, and can retry rate-limited requests. See the [Python SDK section of the docs](/docs#python-sdk) or the source on [GitHub](https://github.com/dahleedam/fraudnova-python)." (keep the heredoc style of the neighbours).

- [ ] **Step 5: Add a `docs/DEPLOY.md` section** `## Python SDK docs (2026-11-06)` after the PHP SDK one: what changed (docs section `#python-sdk`, tabs on six groups, seeder entry `python-sdk` dated 2026-11-07 12:00 UTC, no migration), owner steps as checkboxes: `git pull`; `php8.4 artisan view:clear` then `php8.4 artisan view:cache`; `php8.4 artisan db:seed --class=ChangelogSeeder --force`; push the examples repo (`cd /Users/dahleedam/Herd/fraudnova-examples && git push`); verify `/docs#python-sdk`, the PyPI link resolves once published, `/changelog` shows "Official Python SDK" from 2026-11-07 12:00 UTC.

- [ ] **Step 6: Run** `php -d memory_limit=512M vendor/bin/phpunit tests/Feature/DocsPageTest.php tests/Feature/ChangelogSeederTest.php` (Expected: pass), then the full suite `php -d memory_limit=512M vendor/bin/phpunit` (Expected: all pass), `vendor/bin/phpstan analyse --memory-limit=512M` (0 errors), `vendor/bin/pint --test` (clean apart from the known `docs/legacy-prototype` and `tests/Feature/Webhooks/NowPaymentsWebhookTest.php` exceptions — run `vendor/bin/pint --test --dirty` if the full run only lists those).

- [ ] **Step 7: Commit in the worktree** — `docs: link the official Python SDK from /docs, changelog and deploy notes`.

---

### Task 8: Examples repo link

**Files (under `/Users/dahleedam/Herd/fraudnova-examples`):**
- Modify: `README.md` (the "Official clients" sentence near line 64 and the "**Python**" paragraph near line 112)

- [ ] **Step 1: Edit `README.md`**: in the "Official clients" sentence add "the [Python SDK](https://github.com/dahleedam/fraudnova-python) (`fraudnova` on PyPI)" between the PHP SDK and the n8n node; in the "**Python**" paragraph append: "For application code, use the official Python SDK instead: `pip install fraudnova` ([PyPI](https://pypi.org/project/fraudnova/), [GitHub](https://github.com/dahleedam/fraudnova-python)); it covers every endpoint with typed results, exceptions and automatic batch chunking." mirroring the PHP paragraph.

- [ ] **Step 2: Verify** `grep -c "fraudnova-python" README.md` → 2; `git diff --stat` shows only README.md.

- [ ] **Step 3: Commit** — `docs: link the official Python SDK` (do not push).

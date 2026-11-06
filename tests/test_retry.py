from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Optional

import pytest

from fraudnova.exceptions import ApiError, InvalidArgumentError, RateLimitError
from fraudnova.retry import RetryPolicy, parse_retry_after

CONCURRENCY = (
    '{"success": false, "message": "Too many concurrent requests for this account. Please retry."}'
)
RATE = '{"success": false, "message": "Rate limit exceeded. Try again shortly."}'


def make(body: str, retry_after: Optional[int] = None) -> RateLimitError:
    error = ApiError.from_response(429, body, retry_after)
    assert isinstance(error, RateLimitError)
    return error


def test_parse_retry_after_delta_and_date() -> None:
    now = datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after("5") == 5
    assert parse_retry_after(" 12 ") == 12
    future = datetime(2026, 11, 6, 12, 0, 30, tzinfo=timezone.utc)
    assert parse_retry_after(format_datetime(future, usegmt=True), now) == 30
    past = datetime(2026, 11, 6, 11, 0, 0, tzinfo=timezone.utc)
    assert parse_retry_after(format_datetime(past, usegmt=True), now) == 0
    assert parse_retry_after("soon") is None
    assert parse_retry_after("") is None
    assert parse_retry_after(None) is None


def test_policy_validates() -> None:
    with pytest.raises(InvalidArgumentError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(InvalidArgumentError):
        RetryPolicy(max_retry_after=-1)


def test_delay_for_uses_schedules() -> None:
    policy = RetryPolicy()
    assert policy.delay_for(make(CONCURRENCY), 1) == 1.0
    assert policy.delay_for(make(CONCURRENCY), 2) == 2.0
    assert policy.delay_for(make(RATE), 1) == 5.0
    assert policy.delay_for(make(RATE), 2) == 15.0
    assert policy.delay_for(make(RATE), 3) is None


def test_delay_for_honours_retry_after() -> None:
    assert RetryPolicy().delay_for(make(RATE, 7), 1) == 7.0


def test_delay_for_honours_zero_retry_after() -> None:
    assert RetryPolicy().delay_for(make(RATE, 0), 1) == 0.0


def test_delay_for_stops_when_retry_after_exceeds_max() -> None:
    assert RetryPolicy(max_retry_after=60).delay_for(make(RATE, 120), 1) is None


def test_delay_for_ignores_retry_after_when_disabled() -> None:
    policy = RetryPolicy(honour_retry_after=False)
    assert policy.delay_for(make(RATE, 7), 1) == 5.0


def test_schedule_exhaustion_returns_none() -> None:
    policy = RetryPolicy(max_attempts=10, rate_limit_delays=(5,))
    assert policy.delay_for(make(RATE), 2) is None


def test_sleep_calls_sleeper() -> None:
    calls: list[float] = []
    RetryPolicy(sleeper=calls.append).sleep(2.5)
    assert calls == [2.5]

"""Opt-in retry policy for rate-limited (429) requests."""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Optional

from fraudnova.exceptions import InvalidArgumentError, RateLimitError


def parse_retry_after(value: Optional[str], now: Optional[datetime] = None) -> Optional[int]:
    """Parse a Retry-After header (delta-seconds or HTTP-date) into whole seconds."""
    if value is None:
        return None
    text = value.strip()
    if text == "":
        return None
    if text.isascii() and text.isdigit():
        return int(text)
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    current = now if now is not None else datetime.now(timezone.utc)
    return max(0, int((when - current).total_seconds()))


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    concurrency_delays: Sequence[float] = (1, 2, 4)
    rate_limit_delays: Sequence[float] = (5, 15, 40)
    honour_retry_after: bool = True
    max_retry_after: float = 60
    sleeper: Callable[[float], None] = time.sleep

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise InvalidArgumentError("max_attempts must be at least 1.")
        if self.max_retry_after < 0:
            raise InvalidArgumentError("max_retry_after must not be negative.")

    def delay_for(self, error: RateLimitError, attempt: int) -> Optional[float]:
        """Seconds to wait before retrying after `attempt` (1-based) failed, or None to stop."""
        if attempt >= self.max_attempts:
            return None
        if self.honour_retry_after and error.retry_after is not None:
            if error.retry_after > self.max_retry_after:
                return None
            return float(error.retry_after)
        schedule = self.concurrency_delays if error.is_concurrency_limit else self.rate_limit_delays
        index = attempt - 1
        if index >= len(schedule):
            return None
        return float(schedule[index])

    def sleep(self, seconds: float) -> None:
        self.sleeper(seconds)

"""Exception hierarchy for the FraudNova SDK."""

import json
from typing import Any, Optional


def mask_api_key(api_key: str) -> str:
    """Return a safe, shortened form of an API key for display."""
    if len(api_key) > 12:
        return "fn_…" + api_key[-4:]
    return "fn_…"


class FraudNovaError(Exception):
    """Base class for every error raised by this SDK."""


class InvalidArgumentError(FraudNovaError, ValueError):
    """A client-side input problem; no request was sent."""


class TransportError(FraudNovaError):
    """The HTTP request itself failed (timeout, DNS, TLS)."""


class ApiError(FraudNovaError):
    """The API answered with an error status."""

    def __init__(
        self,
        status_code: int,
        api_message: str,
        body: Optional[dict[str, Any]] = None,
        message: Optional[str] = None,
    ) -> None:
        self.status_code = status_code
        self.api_message = api_message
        self.body: dict[str, Any] = body if body is not None else {}
        super().__init__(
            message
            if message is not None
            else f"FraudNova API error (HTTP {status_code}): {api_message}"
        )

    @classmethod
    def from_response(
        cls, status_code: int, text: str, retry_after: Optional[int] = None
    ) -> "ApiError":
        try:
            decoded: Any = json.loads(text)
        except ValueError:
            decoded = None
        is_json = isinstance(decoded, dict)
        body: dict[str, Any] = decoded if isinstance(decoded, dict) else {}
        envelope = is_json and ("success" in body or "message" in body)

        api_message = ""
        for key in ("message", "error"):
            value = body.get(key)
            if isinstance(value, str) and value != "":
                api_message = value
                break
        if api_message == "":
            stripped = text.strip()
            api_message = stripped[:200] if stripped else f"HTTP {status_code}"

        full: Optional[str] = (
            None if is_json else f"FraudNova API error (HTTP {status_code}): non-JSON response"
        )

        if envelope and status_code == 401:
            return AuthenticationError(status_code, api_message, body, full)
        if envelope and status_code == 402:
            return InsufficientCreditsError(status_code, api_message, body, full)
        if envelope and status_code == 403:
            return AccountSuspendedError(status_code, api_message, body, full)
        if envelope and status_code == 422:
            return ValidationError(status_code, api_message, body, full)
        if status_code == 429:
            return RateLimitError(status_code, api_message, body, retry_after, full)
        if status_code in (502, 503, 504):
            return UpstreamError(
                status_code,
                api_message,
                body,
                status_code == 503 and envelope,
                full,
            )
        return ApiError(status_code, api_message, body, full)


class AuthenticationError(ApiError):
    """401: missing or invalid API key."""


class InsufficientCreditsError(ApiError):
    """402: the account has no credits left."""


class AccountSuspendedError(ApiError):
    """403: the account is suspended."""


class ValidationError(ApiError):
    """422: the request failed validation."""


class RateLimitError(ApiError):
    """429: rate or concurrency limit hit."""

    def __init__(
        self,
        status_code: int,
        api_message: str,
        body: Optional[dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        message: Optional[str] = None,
    ) -> None:
        super().__init__(status_code, api_message, body, message)
        self.retry_after = retry_after

    @property
    def is_concurrency_limit(self) -> bool:
        return "Too many concurrent requests" in self.api_message


class UpstreamError(ApiError):
    """502/503/504: the lookup could not be completed."""

    def __init__(
        self,
        status_code: int,
        api_message: str,
        body: Optional[dict[str, Any]] = None,
        credit_refunded: bool = False,
        message: Optional[str] = None,
    ) -> None:
        text = (
            message
            if message is not None
            else f"FraudNova API error (HTTP {status_code}): {api_message}"
        )
        if credit_refunded:
            text += " The credit for this check was refunded."
        super().__init__(status_code, api_message, body, text)
        self.credit_refunded = credit_refunded


class UnexpectedResponseError(ApiError):
    """A 2xx response whose body is not the success envelope."""

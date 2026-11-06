"""The public FraudNova client."""

from collections.abc import Mapping, Sequence
from typing import Any, Literal, Optional, Union

import httpx

from fraudnova._transport import Transport
from fraudnova.exceptions import InvalidArgumentError, UnexpectedResponseError, mask_api_key
from fraudnova.results import BatchItem, BatchResult, EmailResult, IpResult, PhoneResult, _int
from fraudnova.retry import RetryPolicy

DEFAULT_BASE_URL = "https://fraudnova.com/api/v1"
BATCH_MAX = 100


def _subject(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidArgumentError(f"{name} must be a non-empty string")
    return value.strip()


def _strictness(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1, 2, 3):
        raise InvalidArgumentError("strictness must be an integer from 0 to 3")
    return value


def _country(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().upper() or None


def _data(envelope: Mapping[str, Any]) -> dict[str, Any]:
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise UnexpectedResponseError(200, "Missing data", dict(envelope))
    return data


class Client:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
        retry: Optional[RetryPolicy] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        key = api_key.strip() if isinstance(api_key, str) else ""
        if not key:
            raise InvalidArgumentError("api_key must be a non-empty string")
        if not base_url.lower().startswith(("http://", "https://")):
            raise InvalidArgumentError("base_url must start with http:// or https://")
        self._api_key = key
        self._transport = Transport(key, base_url, timeout, retry, http_client)

    def __repr__(self) -> str:
        masked = mask_api_key(self._api_key)
        return f"Client(api_key={masked!r}, base_url={self._transport.base_url!r})"

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._transport.close()

    # Single checks

    def check_ip(
        self,
        ip: str,
        *,
        strictness: Optional[int] = None,
        mobile: Optional[bool] = None,
        user_agent: Optional[str] = None,
        user_language: Optional[str] = None,
    ) -> IpResult:
        params: dict[str, Union[str, int]] = {"ip": _subject(ip, "ip")}
        level = _strictness(strictness)
        if level is not None:
            params["strictness"] = level
        if mobile is not None:
            params["mobile"] = "true" if mobile else "false"
        if user_agent is not None:
            params["user_agent"] = user_agent
        if user_language is not None:
            params["user_language"] = user_language
        envelope = self._transport.get("/check", params)
        return IpResult.from_dict(_data(envelope), _int(envelope.get("credits_remaining")))

    def check_email(self, email: str) -> EmailResult:
        envelope = self._transport.get("/check/email", {"email": _subject(email, "email")})
        return EmailResult.from_dict(_data(envelope), _int(envelope.get("credits_remaining")))

    def check_phone(self, phone: str, country: Optional[str] = None) -> PhoneResult:
        params: dict[str, Union[str, int]] = {"phone": _subject(phone, "phone")}
        code = _country(country)
        if code:
            params["country"] = code
        envelope = self._transport.get("/check/phone", params)
        return PhoneResult.from_dict(_data(envelope), _int(envelope.get("credits_remaining")))

    # Batch checks

    def check_ips(
        self,
        ips: Sequence[Optional[str]],
        *,
        strictness: Optional[int] = None,
        mobile: Optional[bool] = None,
        user_agent: Optional[str] = None,
        user_language: Optional[str] = None,
    ) -> BatchResult:
        extra: dict[str, Any] = {}
        level = _strictness(strictness)
        if level is not None:
            extra["strictness"] = level
        if mobile is not None:
            extra["mobile"] = mobile
        if user_agent is not None:
            extra["user_agent"] = user_agent
        if user_language is not None:
            extra["user_language"] = user_language
        return self._batch("/check/batch", "ips", "ip", ips, extra)

    def check_emails(self, emails: Sequence[Optional[str]]) -> BatchResult:
        return self._batch("/check/email/batch", "emails", "email", emails, {})

    def check_phones(
        self, phones: Sequence[Optional[str]], country: Optional[str] = None
    ) -> BatchResult:
        extra: dict[str, Any] = {}
        code = _country(country)
        if code:
            extra["country"] = code
        return self._batch("/check/phone/batch", "phones", "phone", phones, extra)

    def _batch(
        self,
        path: str,
        field: str,
        kind: Literal["ip", "email", "phone"],
        subjects: Sequence[Optional[str]],
        extra: Mapping[str, Any],
    ) -> BatchResult:
        if len(subjects) == 0:
            raise InvalidArgumentError(f"{field} must not be empty")
        cleaned: list[Optional[str]] = []
        for index, item in enumerate(subjects):
            if item is not None and not isinstance(item, str):
                raise InvalidArgumentError(f"{field}[{index}] must be a string or None")
            cleaned.append(item.strip() if item is not None else None)
        items: list[BatchItem] = []
        credits = 0
        for start in range(0, len(cleaned), BATCH_MAX):
            body: dict[str, Any] = {field: cleaned[start : start + BATCH_MAX], **extra}
            envelope = self._transport.post(path, body)
            if not isinstance(envelope.get("results"), list):
                raise UnexpectedResponseError(200, "Missing results", dict(envelope))
            part = BatchResult.from_dict(envelope, kind)
            items.extend(part.items)
            credits = part.credits_remaining
        return BatchResult(items=items, credits_remaining=credits)

    # Account

    def balance(self) -> int:
        envelope = self._transport.get("/balance")
        credits = _int(envelope.get("credits_remaining"))
        if credits is None:
            raise UnexpectedResponseError(200, "Missing credits_remaining", dict(envelope))
        return credits

    def my_ip(self) -> str:
        envelope = self._transport.get("/my-ip", authenticated=False)
        ip = envelope.get("ip")
        if not isinstance(ip, str) or not ip:
            raise UnexpectedResponseError(200, "Missing ip", dict(envelope))
        return ip

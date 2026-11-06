"""Typed, leniently parsed results for IP, email and phone checks."""

import math
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, ClassVar, Literal, Optional, Union

_WHOLE = re.compile(r"-?[0-9]+")
_DECIMAL = re.compile(r"-?[0-9]+\.[0-9]+")


def _bool(value: Any) -> Optional[bool]:
    return value if isinstance(value, bool) else None


def _str(value: Any) -> Optional[str]:
    return value if isinstance(value, str) else None


def _int(value: Any) -> Optional[int]:
    """Ints and whole-number strings as-is; floats and decimal strings round half away from zero."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    number: Optional[float] = None
    if isinstance(value, str):
        if _WHOLE.fullmatch(value):
            return int(value)
        if _DECIMAL.fullmatch(value):
            number = float(value)
    elif isinstance(value, float):
        number = value
    if number is None or not math.isfinite(number):
        return None
    rounded = math.floor(abs(number) + 0.5)
    return -rounded if number < 0 else rounded


_coerce_int = _int


@dataclass(frozen=True)
class DateInfo:
    human: Optional[str]
    timestamp: Optional[int]
    iso: Optional[str]

    @classmethod
    def from_value(cls, value: Any) -> Optional["DateInfo"]:
        if isinstance(value, str):
            return cls(human=value, timestamp=None, iso=None)
        if isinstance(value, Mapping):
            return cls(
                human=_str(value.get("human")),
                timestamp=_int(value.get("timestamp")),
                iso=_str(value.get("iso")),
            )
        return None


class _FlaggableResult:
    DEFAULT_FLAG_ON: ClassVar[tuple[str, ...]] = ()
    raw: dict[str, Any]

    def flag_reasons(
        self, risk_threshold: int = 75, flag_on: Optional[Sequence[str]] = None
    ) -> list[str]:
        reasons: list[str] = []
        if (_int(self.raw.get("fraud_score")) or 0) >= risk_threshold:
            reasons.append("fraud_score")
        names = self.DEFAULT_FLAG_ON if flag_on is None else flag_on
        reasons.extend(name for name in names if self.raw.get(name) is True)
        return reasons

    def flagged(self, risk_threshold: int = 75, flag_on: Optional[Sequence[str]] = None) -> bool:
        return bool(self.flag_reasons(risk_threshold, flag_on))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.raw)


@dataclass(frozen=True)
class IpResult(_FlaggableResult):
    DEFAULT_FLAG_ON: ClassVar[tuple[str, ...]] = ("proxy", "vpn", "tor")

    fraud_score: int
    proxy: Optional[bool]
    vpn: Optional[bool]
    tor: Optional[bool]
    active_vpn: Optional[bool]
    active_tor: Optional[bool]
    recent_abuse: Optional[bool]
    bot_status: Optional[bool]
    country_code: Optional[str]
    region: Optional[str]
    city: Optional[str]
    isp: Optional[str]
    organization: Optional[str]
    asn: Optional[int]
    operating_system: Optional[str]
    browser: Optional[str]
    device_brand: Optional[str]
    device_model: Optional[str]
    credits_remaining: Optional[int]
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], credits_remaining: Optional[int] = None
    ) -> "IpResult":
        raw = data if isinstance(data, dict) else dict(data)
        return cls(
            fraud_score=_int(raw.get("fraud_score")) or 0,
            proxy=_bool(raw.get("proxy")),
            vpn=_bool(raw.get("vpn")),
            tor=_bool(raw.get("tor")),
            active_vpn=_bool(raw.get("active_vpn")),
            active_tor=_bool(raw.get("active_tor")),
            recent_abuse=_bool(raw.get("recent_abuse")),
            bot_status=_bool(raw.get("bot_status")),
            country_code=_str(raw.get("country_code")),
            region=_str(raw.get("region")),
            city=_str(raw.get("city")),
            isp=_str(raw.get("ISP")),
            organization=_str(raw.get("organization")),
            asn=_int(raw.get("ASN")),
            operating_system=_str(raw.get("operating_system")),
            browser=_str(raw.get("browser")),
            device_brand=_str(raw.get("device_brand")),
            device_model=_str(raw.get("device_model")),
            credits_remaining=credits_remaining,
            raw=raw,
        )


@dataclass(frozen=True)
class EmailResult(_FlaggableResult):
    DEFAULT_FLAG_ON: ClassVar[tuple[str, ...]] = ("disposable",)

    fraud_score: int
    valid: Optional[bool]
    disposable: Optional[bool]
    catch_all: Optional[bool]
    generic: Optional[bool]
    common: Optional[bool]
    dns_valid: Optional[bool]
    honeypot: Optional[bool]
    frequent_complainer: Optional[bool]
    suspect: Optional[bool]
    recent_abuse: Optional[bool]
    leaked: Optional[bool]
    risky_tld: Optional[bool]
    spf_record: Optional[bool]
    dmarc_record: Optional[bool]
    smtp_score: Optional[int]
    overall_score: Optional[int]
    deliverability: Optional[str]
    spam_trap_score: Optional[str]
    result_type: Optional[str]
    sanitized_email: Optional[str]
    first_seen: Optional[DateInfo]
    domain_age: Optional[DateInfo]
    credits_remaining: Optional[int]
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], credits_remaining: Optional[int] = None
    ) -> "EmailResult":
        raw = data if isinstance(data, dict) else dict(data)
        return cls(
            fraud_score=_int(raw.get("fraud_score")) or 0,
            valid=_bool(raw.get("valid")),
            disposable=_bool(raw.get("disposable")),
            catch_all=_bool(raw.get("catch_all")),
            generic=_bool(raw.get("generic")),
            common=_bool(raw.get("common")),
            dns_valid=_bool(raw.get("dns_valid")),
            honeypot=_bool(raw.get("honeypot")),
            frequent_complainer=_bool(raw.get("frequent_complainer")),
            suspect=_bool(raw.get("suspect")),
            recent_abuse=_bool(raw.get("recent_abuse")),
            leaked=_bool(raw.get("leaked")),
            risky_tld=_bool(raw.get("risky_tld")),
            spf_record=_bool(raw.get("spf_record")),
            dmarc_record=_bool(raw.get("dmarc_record")),
            smtp_score=_int(raw.get("smtp_score")),
            overall_score=_int(raw.get("overall_score")),
            deliverability=_str(raw.get("deliverability")),
            spam_trap_score=_str(raw.get("spam_trap_score")),
            result_type=_str(raw.get("result_type")),
            sanitized_email=_str(raw.get("sanitized_email")),
            first_seen=DateInfo.from_value(raw.get("first_seen")),
            domain_age=DateInfo.from_value(raw.get("domain_age")),
            credits_remaining=credits_remaining,
            raw=raw,
        )


@dataclass(frozen=True)
class PhoneResult(_FlaggableResult):
    DEFAULT_FLAG_ON: ClassVar[tuple[str, ...]] = ("VOIP", "risky")

    fraud_score: int
    valid: Optional[bool]
    recent_abuse: Optional[bool]
    voip: Optional[bool]
    prepaid: Optional[bool]
    risky: Optional[bool]
    active: Optional[bool]
    do_not_call: Optional[bool]
    leaked: Optional[bool]
    spammer: Optional[bool]
    dialing_code: Optional[int]
    carrier: Optional[str]
    line_type: Optional[str]
    country: Optional[str]
    region: Optional[str]
    city: Optional[str]
    timezone: Optional[str]
    zip_code: Optional[str]
    active_status: Optional[str]
    formatted: Optional[str]
    local_format: Optional[str]
    credits_remaining: Optional[int]
    raw: dict[str, Any] = field(repr=False)

    @classmethod
    def from_dict(
        cls, data: Mapping[str, Any], credits_remaining: Optional[int] = None
    ) -> "PhoneResult":
        raw = data if isinstance(data, dict) else dict(data)
        return cls(
            fraud_score=_int(raw.get("fraud_score")) or 0,
            valid=_bool(raw.get("valid")),
            recent_abuse=_bool(raw.get("recent_abuse")),
            voip=_bool(raw.get("VOIP")),
            prepaid=_bool(raw.get("prepaid")),
            risky=_bool(raw.get("risky")),
            active=_bool(raw.get("active")),
            do_not_call=_bool(raw.get("do_not_call")),
            leaked=_bool(raw.get("leaked")),
            spammer=_bool(raw.get("spammer")),
            dialing_code=_int(raw.get("dialing_code")),
            carrier=_str(raw.get("carrier")),
            line_type=_str(raw.get("line_type")),
            country=_str(raw.get("country")),
            region=_str(raw.get("region")),
            city=_str(raw.get("city")),
            timezone=_str(raw.get("timezone")),
            zip_code=_str(raw.get("zip_code")),
            active_status=_str(raw.get("active_status")),
            formatted=_str(raw.get("formatted")),
            local_format=_str(raw.get("local_format")),
            credits_remaining=credits_remaining,
            raw=raw,
        )


Result = Union[IpResult, EmailResult, PhoneResult]


@dataclass(frozen=True)
class BatchItem:
    subject: str
    success: bool
    result: Optional[Result]
    error: Optional[str]

    def is_invalid(self) -> bool:
        return self.error in ("invalid_ip", "invalid_email", "invalid_phone")

    def is_insufficient_credits(self) -> bool:
        return self.error == "insufficient_credits"

    def is_upstream_failed(self) -> bool:
        return self.error == "upstream_failed"


@dataclass(frozen=True)
class BatchResult:
    items: list[BatchItem]
    credits_remaining: int

    @classmethod
    def from_dict(
        cls, envelope: Mapping[str, Any], kind: Literal["ip", "email", "phone"]
    ) -> "BatchResult":
        raw_items = envelope.get("results")
        items: list[BatchItem] = []
        if isinstance(raw_items, list):
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                success = _bool(item.get("success")) or False
                data = item.get("data")
                result: Optional[Result] = None
                if success and isinstance(data, dict):
                    if kind == "ip":
                        result = IpResult.from_dict(data)
                    elif kind == "email":
                        result = EmailResult.from_dict(data)
                    else:
                        result = PhoneResult.from_dict(data)
                items.append(
                    BatchItem(
                        subject=_str(item.get(kind)) or "",
                        success=success,
                        result=result,
                        error=_str(item.get("error")),
                    )
                )
        return cls(items=items, credits_remaining=_int(envelope.get("credits_remaining")) or 0)

    def successful(self) -> list[BatchItem]:
        return [i for i in self.items if i.success]

    def failed(self) -> list[BatchItem]:
        return [i for i in self.items if not i.success]

    def has_failures(self) -> bool:
        return any(not i.success for i in self.items)

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self) -> Iterator[BatchItem]:
        return iter(self.items)

    def __getitem__(self, index: int) -> BatchItem:
        return self.items[index]

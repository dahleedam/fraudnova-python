from typing import Any

from fraudnova.results import (
    BatchResult,
    DateInfo,
    EmailResult,
    IpResult,
    PhoneResult,
    _int,
)


def test_int_coercion() -> None:
    assert _int(5) == 5
    assert _int("88") == 88
    assert _int(87.5) == 88
    assert _int(-87.5) == -88
    assert _int("87.5") == 88
    assert _int(True) is None
    assert _int("abc") is None
    assert _int(float("nan")) is None
    assert _int(float("inf")) is None
    assert _int(None) is None


def ip_fixture() -> dict[str, Any]:
    return {
        "fraud_score": 90,
        "proxy": True,
        "vpn": False,
        "tor": False,
        "active_vpn": False,
        "active_tor": False,
        "recent_abuse": True,
        "bot_status": False,
        "country_code": "US",
        "region": "California",
        "city": "Mountain View",
        "ISP": "Google LLC",
        "organization": "Google",
        "ASN": 15169,
        "operating_system": "Windows 10",
        "browser": "Chrome",
        "device_brand": "Dell",
        "device_model": "XPS",
        "extra": "kept",
    }


def test_ip_result_maps_every_field() -> None:
    data = ip_fixture()
    r = IpResult.from_dict(data, credits_remaining=42)
    assert r.fraud_score == 90
    assert r.proxy is True
    assert r.vpn is False
    assert r.tor is False
    assert r.active_vpn is False
    assert r.active_tor is False
    assert r.recent_abuse is True
    assert r.bot_status is False
    assert r.country_code == "US"
    assert r.region == "California"
    assert r.city == "Mountain View"
    assert r.isp == "Google LLC"
    assert r.organization == "Google"
    assert r.asn == 15169
    assert r.operating_system == "Windows 10"
    assert r.browser == "Chrome"
    assert r.device_brand == "Dell"
    assert r.device_model == "XPS"
    assert r.credits_remaining == 42
    assert r.raw is data
    copy = r.to_dict()
    assert copy == data
    assert copy is not data
    assert "raw" not in repr(r)


def test_ip_result_missing_fields_default_to_none_and_zero_score() -> None:
    r = IpResult.from_dict({})
    assert r.fraud_score == 0
    assert r.proxy is None
    assert r.isp is None
    assert r.asn is None
    assert r.credits_remaining is None
    assert r.flag_reasons() == []
    assert r.flagged() is False


def test_mistyped_field_is_none_but_kept_in_raw() -> None:
    r = IpResult.from_dict({"proxy": "yes", "fraud_score": "abc", "ASN": [1]})
    assert r.proxy is None
    assert r.raw["proxy"] == "yes"
    assert r.fraud_score == 0
    assert r.asn is None


def test_fractional_score_still_flags() -> None:
    r = IpResult.from_dict({"fraud_score": 87.5})
    assert r.fraud_score == 88
    assert r.flagged() is True
    assert r.flag_reasons() == ["fraud_score"]


def test_flag_defaults_per_type() -> None:
    assert IpResult.DEFAULT_FLAG_ON == ("proxy", "vpn", "tor")
    assert EmailResult.DEFAULT_FLAG_ON == ("disposable",)
    assert PhoneResult.DEFAULT_FLAG_ON == ("VOIP", "risky")
    assert IpResult.from_dict({"proxy": True}).flag_reasons() == ["proxy"]
    assert EmailResult.from_dict({"disposable": True}).flag_reasons() == ["disposable"]
    assert PhoneResult.from_dict({"VOIP": True}).flag_reasons() == ["VOIP"]
    assert IpResult.from_dict({"vpn": 1}).flagged() is False
    assert IpResult.from_dict({"fraud_score": 74}).flagged() is False
    assert IpResult.from_dict({"fraud_score": 75}).flag_reasons() == ["fraud_score"]


def test_custom_threshold_and_flag_on() -> None:
    r = IpResult.from_dict({"fraud_score": 50, "proxy": True, "tor": True})
    assert r.flag_reasons() == ["proxy", "tor"]
    assert r.flag_reasons(risk_threshold=40, flag_on=["tor"]) == ["fraud_score", "tor"]
    assert r.flag_reasons(flag_on=[]) == []
    assert r.flagged(risk_threshold=50, flag_on=()) is True


def test_email_date_fields() -> None:
    iso = "2020-09-13T12:26:40+00:00"
    info = {"human": "3 years ago", "timestamp": 1600000000, "iso": iso}
    r = EmailResult.from_dict({"first_seen": info, "domain_age": "2020-09-13"})
    assert r.first_seen == DateInfo(human="3 years ago", timestamp=1600000000, iso=iso)
    assert r.domain_age == DateInfo(human="2020-09-13", timestamp=None, iso=None)
    r2 = EmailResult.from_dict({"first_seen": None, "domain_age": 7})
    assert r2.first_seen is None
    assert r2.domain_age is None
    assert EmailResult.from_dict({}).first_seen is None


def test_email_result_maps_fields() -> None:
    r = EmailResult.from_dict(
        {
            "valid": True,
            "disposable": False,
            "catch_all": True,
            "dns_valid": True,
            "smtp_score": "3",
            "overall_score": 4,
            "deliverability": "high",
            "sanitized_email": "a@b.c",
            "fraud_score": 10,
        },
        credits_remaining=9,
    )
    assert r.valid is True
    assert r.catch_all is True
    assert r.dns_valid is True
    assert r.smtp_score == 3
    assert r.overall_score == 4
    assert r.deliverability == "high"
    assert r.sanitized_email == "a@b.c"
    assert r.credits_remaining == 9


def test_phone_result_maps_voip_and_strings() -> None:
    r = PhoneResult.from_dict(
        {
            "VOIP": True,
            "risky": False,
            "dialing_code": 1,
            "carrier": "Verizon",
            "line_type": "Wireless",
            "formatted": "+18176791808",
            "local_format": "(817) 679-1808",
            "zip_code": "76101",
            "name": 5,
        }
    )
    assert r.voip is True
    assert r.risky is False
    assert r.dialing_code == 1
    assert r.carrier == "Verizon"
    assert r.line_type == "Wireless"
    assert r.formatted == "+18176791808"
    assert r.local_format == "(817) 679-1808"
    assert r.zip_code == "76101"
    assert r.flag_reasons() == ["VOIP"]


def test_batch_result_parses_items_and_helpers() -> None:
    envelope = {
        "success": True,
        "results": [
            {"ip": "8.8.8.8", "success": True, "data": {"fraud_score": 5, "proxy": False}},
            {"ip": "bad", "success": False, "error": "invalid_ip"},
            {"ip": "1.1.1.1", "success": False, "error": "insufficient_credits"},
            {"ip": "2.2.2.2", "success": False, "error": "upstream_failed"},
            {"ip": "3.3.3.3", "success": False, "error": "weird"},
        ],
        "credits_remaining": 7,
    }
    batch = BatchResult.from_dict(envelope, "ip")
    assert len(batch) == 5
    assert batch.credits_remaining == 7
    assert [i.subject for i in batch] == ["8.8.8.8", "bad", "1.1.1.1", "2.2.2.2", "3.3.3.3"]
    first = batch[0]
    assert first.success is True
    assert isinstance(first.result, IpResult)
    assert first.result.credits_remaining is None
    assert first.error is None
    assert [i.subject for i in batch.successful()] == ["8.8.8.8"]
    assert len(batch.failed()) == 4
    assert batch.has_failures() is True
    assert batch[1].is_invalid() is True
    assert batch[1].result is None
    assert batch[2].is_insufficient_credits() is True
    assert batch[3].is_upstream_failed() is True
    weird = batch[4]
    assert weird.error == "weird"
    assert not (weird.is_invalid() or weird.is_insufficient_credits() or weird.is_upstream_failed())


def test_batch_kinds_use_matching_subject_key_and_type() -> None:
    e = BatchResult.from_dict(
        {"results": [{"email": "a@b.c", "success": True, "data": {"disposable": True}}]},
        "email",
    )
    assert isinstance(e[0].result, EmailResult)
    assert e[0].subject == "a@b.c"
    p = BatchResult.from_dict(
        {"results": [{"phone": "1555", "success": False, "error": "invalid_phone"}]}, "phone"
    )
    assert p[0].subject == "1555"
    assert p[0].is_invalid() is True


def test_batch_item_success_without_data() -> None:
    batch = BatchResult.from_dict({"results": [{"email": "a@b.c", "success": True}]}, "email")
    assert batch[0].result is None
    assert batch[0].success is True
    assert (
        BatchResult.from_dict({"results": [{"ip": "1.1.1.1", "success": "yes"}]}, "ip")[0].success
        is False
    )


def test_batch_result_tolerates_garbage() -> None:
    empty = BatchResult.from_dict({}, "ip")
    assert len(empty) == 0
    assert empty.credits_remaining == 0
    assert empty.has_failures() is False
    batch = BatchResult.from_dict(
        {"results": ["junk", None, {"ip": "1.1.1.1", "success": False}]}, "ip"
    )
    assert len(batch) == 1
    assert batch[0].subject == "1.1.1.1"
    assert BatchResult.from_dict({"results": "nope", "credits_remaining": "x"}, "ip").items == []

import pytest

from fraudnova.exceptions import (
    AccountSuspendedError,
    ApiError,
    AuthenticationError,
    FraudNovaError,
    InsufficientCreditsError,
    InvalidArgumentError,
    RateLimitError,
    TransportError,
    UnexpectedResponseError,
    UpstreamError,
    ValidationError,
    mask_api_key,
)

ENVELOPE = '{"success": false, "message": "x"}'


def test_every_error_is_a_fraudnova_error() -> None:
    for cls in (
        InvalidArgumentError,
        TransportError,
        ApiError,
        AuthenticationError,
        InsufficientCreditsError,
        AccountSuspendedError,
        ValidationError,
        RateLimitError,
        UpstreamError,
        UnexpectedResponseError,
    ):
        assert issubclass(cls, FraudNovaError)
    assert issubclass(InvalidArgumentError, ValueError)
    assert issubclass(RateLimitError, ApiError)


@pytest.mark.parametrize(
    ("status", "cls"),
    [
        (401, AuthenticationError),
        (402, InsufficientCreditsError),
        (403, AccountSuspendedError),
        (422, ValidationError),
        (429, RateLimitError),
        (502, UpstreamError),
        (503, UpstreamError),
        (504, UpstreamError),
        (500, ApiError),
        (418, ApiError),
    ],
)
def test_status_dispatch(status: int, cls: type[ApiError]) -> None:
    error = ApiError.from_response(status, ENVELOPE)
    assert type(error) is cls
    assert error.status_code == status


def test_message_format() -> None:
    error = ApiError.from_response(402, '{"success": false, "message": "Insufficient credits."}')
    assert str(error) == "FraudNova API error (HTTP 402): Insufficient credits."
    assert error.api_message == "Insufficient credits."
    assert error.body["success"] is False


def test_error_key_is_accepted_as_message() -> None:
    error = ApiError.from_response(422, '{"success": false, "error": "Bad IP"}')
    assert type(error) is ValidationError
    assert error.api_message == "Bad IP"


def test_html_401_is_plain_api_error() -> None:
    html = "<html>" + "x" * 300 + "</html>\n"
    error = ApiError.from_response(401, html)
    assert type(error) is ApiError
    assert error.api_message == html.strip()[:200]
    assert str(error).endswith("non-JSON response")


def test_html_429_is_rate_limit_error() -> None:
    error = ApiError.from_response(429, "<html>slow down</html>", retry_after=3)
    assert type(error) is RateLimitError
    assert isinstance(error, RateLimitError)
    assert error.retry_after == 3


def test_503_envelope_marks_credit_refunded() -> None:
    error = ApiError.from_response(503, '{"success": false, "message": "Upstream lookup failed."}')
    assert isinstance(error, UpstreamError)
    assert error.credit_refunded is True
    assert str(error).endswith("The credit for this check was refunded.")


def test_503_html_is_not_refunded() -> None:
    error = ApiError.from_response(503, "<html>bad gateway</html>")
    assert isinstance(error, UpstreamError)
    assert error.credit_refunded is False
    assert "refunded" not in str(error)


def test_rate_limit_retry_after_and_concurrency() -> None:
    body = (
        '{"success": false, "message": '
        '"Too many concurrent requests for this account. Please retry."}'
    )
    error = ApiError.from_response(429, body, retry_after=7)
    assert isinstance(error, RateLimitError)
    assert error.retry_after == 7
    assert error.is_concurrency_limit is True
    other = ApiError.from_response(429, ENVELOPE)
    assert isinstance(other, RateLimitError)
    assert other.is_concurrency_limit is False


def test_empty_body_message_is_http_status() -> None:
    error = ApiError.from_response(500, "")
    assert error.api_message == "HTTP 500"


def test_mask_api_key() -> None:
    assert mask_api_key("fn_" + "a" * 20 + "WXYZ") == "fn_…WXYZ"
    assert mask_api_key("fn_short") == "fn_…"

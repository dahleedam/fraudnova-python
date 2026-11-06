"""Official Python SDK for the FraudNova fraud-detection API."""

from ._version import __version__
from .client import BATCH_MAX, DEFAULT_BASE_URL, Client
from .exceptions import (
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
)
from .results import BatchItem, BatchResult, DateInfo, EmailResult, IpResult, PhoneResult
from .retry import RetryPolicy

__all__ = [
    "BATCH_MAX",
    "DEFAULT_BASE_URL",
    "AccountSuspendedError",
    "ApiError",
    "AuthenticationError",
    "BatchItem",
    "BatchResult",
    "Client",
    "DateInfo",
    "EmailResult",
    "FraudNovaError",
    "InsufficientCreditsError",
    "InvalidArgumentError",
    "IpResult",
    "PhoneResult",
    "RateLimitError",
    "RetryPolicy",
    "TransportError",
    "UnexpectedResponseError",
    "UpstreamError",
    "ValidationError",
    "__version__",
]

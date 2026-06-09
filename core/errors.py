from __future__ import annotations

from dataclasses import dataclass
from typing import Any


INVALID_ARGUMENT = "INVALID_ARGUMENT"
AUTH_REQUIRED = "AUTH_REQUIRED"
POLICY_DENIED = "POLICY_DENIED"
RATE_LIMITED = "RATE_LIMITED"
ARTIFACT_NOT_FOUND = "ARTIFACT_NOT_FOUND"
ARTIFACT_FORBIDDEN = "ARTIFACT_FORBIDDEN"
PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
PROVIDER_REJECTED = "PROVIDER_REJECTED"
PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
UNSUPPORTED_MEDIA_TYPE = "UNSUPPORTED_MEDIA_TYPE"
INTERNAL_ERROR = "INTERNAL_ERROR"

STABLE_ERROR_CODES = {
    INVALID_ARGUMENT,
    AUTH_REQUIRED,
    POLICY_DENIED,
    RATE_LIMITED,
    ARTIFACT_NOT_FOUND,
    ARTIFACT_FORBIDDEN,
    PROVIDER_UNAVAILABLE,
    PROVIDER_REJECTED,
    PROVIDER_TIMEOUT,
    UNSUPPORTED_MEDIA_TYPE,
    INTERNAL_ERROR,
}


@dataclass(slots=True)
class GatewayError(Exception):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.code not in STABLE_ERROR_CODES:
            self.code = INTERNAL_ERROR
            self.retryable = False


def internal_error() -> GatewayError:
    return GatewayError(INTERNAL_ERROR, "internal gateway error", retryable=False)

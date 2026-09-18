"""Normalized error handling and classifications for Google Workspace APIs."""
from __future__ import annotations

import socket
from enum import StrEnum
from typing import Optional


class GoogleErrorCode(StrEnum):
    AUTH_REQUIRED = "AUTH_REQUIRED"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    SCOPE_MISSING = "SCOPE_MISSING"
    RATE_LIMITED = "RATE_LIMITED"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    CONFLICT = "CONFLICT"
    PROVIDER_ERROR = "PROVIDER_ERROR"


class GoogleProviderError(Exception):
    """Normalized domain error for all Google Workspace service integrations."""

    def __init__(
        self,
        code: GoogleErrorCode,
        message: str,
        service: str = "google",
        status_code: Optional[int] = None,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.message = message
        self.service = service
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(f"[{service.upper()}:{code.value}] {message}")



def normalize_google_error(exc: Exception, service: str = "google") -> GoogleProviderError:
    """Translate raw Google HttpError, network timeouts, or OS errors into a normalized GoogleProviderError."""
    if isinstance(exc, GoogleProviderError):
        return exc

    err_str = str(exc).lower()

    # Network / socket / timeout errors
    if isinstance(exc, (socket.timeout, TimeoutError)) or "timed out" in err_str:
        return GoogleProviderError(
            code=GoogleErrorCode.TIMEOUT,
            message="Request to Google API timed out.",
            service=service,
            retryable=True,
        )

    if isinstance(exc, (socket.gaierror, ConnectionError, OSError)) or "connection" in err_str or "unreachable" in err_str:
        return GoogleProviderError(
            code=GoogleErrorCode.NETWORK_UNAVAILABLE,
            message="Google network service is currently unreachable.",
            service=service,
            retryable=True,
        )

    # Inspect Google API HttpError
    status_code: Optional[int] = getattr(exc, "status_code", None)
    if not status_code and hasattr(exc, "resp") and hasattr(exc.resp, "status"):
        try:
            status_code = int(exc.resp.status)
        except (ValueError, TypeError):
            pass

    if status_code == 401:
        return GoogleProviderError(
            code=GoogleErrorCode.AUTH_REQUIRED,
            message="Authentication credentials invalid or expired. Reauthorization required.",
            service=service,
            status_code=401,
            retryable=False,
        )

    if status_code == 403:
        if "rate" in err_str or "quota" in err_str:
            return GoogleProviderError(
                code=GoogleErrorCode.QUOTA_EXCEEDED,
                message="Google API rate limit or quota exceeded.",
                service=service,
                status_code=403,
                retryable=True,
            )
        return GoogleProviderError(
            code=GoogleErrorCode.SCOPE_MISSING,
            message="Operation requires additional OAuth permissions.",
            service=service,
            status_code=403,
            retryable=False,
        )

    if status_code == 429:
        return GoogleProviderError(
            code=GoogleErrorCode.RATE_LIMITED,
            message="Too many requests sent to Google API.",
            service=service,
            status_code=429,
            retryable=True,
        )

    if status_code == 404:
        return GoogleProviderError(
            code=GoogleErrorCode.NOT_FOUND,
            message="The requested Google resource was not found.",
            service=service,
            status_code=404,
            retryable=False,
        )

    if status_code == 409:
        return GoogleProviderError(
            code=GoogleErrorCode.CONFLICT,
            message="Resource conflict detected on Google API.",
            service=service,
            status_code=409,
            retryable=False,
        )

    return GoogleProviderError(
        code=GoogleErrorCode.PROVIDER_ERROR,
        message=f"Google API call failed: {exc}",
        service=service,
        status_code=status_code,
        retryable=False,
    )

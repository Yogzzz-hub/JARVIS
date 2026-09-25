"""Capability and Scope Registry for Least-Privilege Google Workspace Access."""
from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional, Set, Tuple

if TYPE_CHECKING:
    from jarvis.integrations.google.auth.models import GoogleAccount


class GoogleCapability(StrEnum):
    # Gmail capabilities
    GMAIL_METADATA = "GMAIL_METADATA"
    GMAIL_READ = "GMAIL_READ"
    GMAIL_COMPOSE = "GMAIL_COMPOSE"
    GMAIL_DRAFT = "GMAIL_DRAFT"
    GMAIL_SEND = "GMAIL_SEND"

    # Calendar capabilities
    CALENDAR_READ = "CALENDAR_READ"
    CALENDAR_WRITE = "CALENDAR_WRITE"

    # Drive capabilities
    DRIVE_FILE_READ = "DRIVE_FILE_READ"
    DRIVE_FILE_WRITE = "DRIVE_FILE_WRITE"
    DRIVE_APP_FILE = "DRIVE_APP_FILE"
    DRIVE_APP_FILE_READ = "DRIVE_APP_FILE_READ"
    DRIVE_APP_FILE_WRITE = "DRIVE_APP_FILE_WRITE"
    DRIVE_BROAD_METADATA = "DRIVE_BROAD_METADATA"
    DRIVE_BROAD_READ = "DRIVE_BROAD_READ"
    DRIVE_READONLY = "DRIVE_READONLY"
    DRIVE_METADATA = "DRIVE_METADATA"


# Map each capability to its exact Google OAuth 2.0 scope URI
CAPABILITY_SCOPES: Dict[GoogleCapability, Tuple[str, ...]] = {
    GoogleCapability.GMAIL_METADATA: (
        "https://www.googleapis.com/auth/gmail.metadata",
    ),
    GoogleCapability.GMAIL_READ: (
        "https://www.googleapis.com/auth/gmail.readonly",
    ),
    GoogleCapability.GMAIL_COMPOSE: (
        "https://www.googleapis.com/auth/gmail.compose",
    ),
    GoogleCapability.GMAIL_DRAFT: (
        "https://www.googleapis.com/auth/gmail.compose",
    ),
    GoogleCapability.GMAIL_SEND: (
        "https://www.googleapis.com/auth/gmail.send",
    ),
    GoogleCapability.CALENDAR_READ: (
        "https://www.googleapis.com/auth/calendar.events.readonly",
    ),
    GoogleCapability.CALENDAR_WRITE: (
        "https://www.googleapis.com/auth/calendar.events",
    ),
    GoogleCapability.DRIVE_FILE_READ: (
        "https://www.googleapis.com/auth/drive.file",
    ),
    GoogleCapability.DRIVE_FILE_WRITE: (
        "https://www.googleapis.com/auth/drive.file",
    ),
    GoogleCapability.DRIVE_APP_FILE: (
        "https://www.googleapis.com/auth/drive.file",
    ),
    GoogleCapability.DRIVE_APP_FILE_READ: (
        "https://www.googleapis.com/auth/drive.file",
    ),
    GoogleCapability.DRIVE_APP_FILE_WRITE: (
        "https://www.googleapis.com/auth/drive.file",
    ),
    GoogleCapability.DRIVE_BROAD_METADATA: (
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ),
    GoogleCapability.DRIVE_BROAD_READ: (
        "https://www.googleapis.com/auth/drive.readonly",
    ),
    GoogleCapability.DRIVE_READONLY: (
        "https://www.googleapis.com/auth/drive.readonly",
    ),
    GoogleCapability.DRIVE_METADATA: (
        "https://www.googleapis.com/auth/drive.metadata.readonly",
    ),
}

# Initial minimal capabilities requested per service (Least Privilege)
SERVICE_DEFAULT_CAPABILITIES: Dict[str, Tuple[GoogleCapability, ...]] = {
    "gmail": (GoogleCapability.GMAIL_READ, GoogleCapability.GMAIL_DRAFT),
    "calendar": (GoogleCapability.CALENDAR_READ,),
    "drive": (GoogleCapability.DRIVE_APP_FILE_READ, GoogleCapability.DRIVE_APP_FILE_WRITE),
    "all": (
        GoogleCapability.GMAIL_READ,
        GoogleCapability.GMAIL_DRAFT,
        GoogleCapability.CALENDAR_READ,
        GoogleCapability.DRIVE_APP_FILE_READ,
        GoogleCapability.DRIVE_APP_FILE_WRITE,
    ),
}


class AuthorizationRequiredError(Exception):
    """Raised when an operation requires an OAuth scope that has not been granted yet."""

    def __init__(
        self,
        capability: GoogleCapability,
        missing_scopes: Set[str],
        account_id: str = "primary",
        message: str | None = None,
    ) -> None:
        self.capability = capability
        self.missing_scopes = missing_scopes
        self.account_id = account_id
        if not message:
            message = (
                f"AUTHORIZATION_REQUIRED: Action requires '{capability.value}' permission, "
                f"which is not currently granted. Missing scope(s): {', '.join(sorted(missing_scopes))}. "
                "Please run 'python -m jarvis.google connect' to authorize this capability."
            )
        super().__init__(message)


class ScopeRegistry:
    """Registry managing capability mapping and scope verification."""

    @staticmethod
    def get_scopes_for_capability(capability: GoogleCapability) -> Tuple[str, ...]:
        return CAPABILITY_SCOPES.get(capability, ())

    @classmethod
    def get_scopes_for_capabilities(cls, capabilities: Iterable[GoogleCapability]) -> Set[str]:
        scopes: Set[str] = set()
        for cap in capabilities:
            scopes.update(cls.get_scopes_for_capability(cap))
        return scopes

    @classmethod
    def get_missing_scopes(
        cls, account: GoogleAccount, required_capability: GoogleCapability
    ) -> Set[str]:
        required = set(cls.get_scopes_for_capability(required_capability))
        return required - set(account.granted_scopes)

    @classmethod
    def validate_capability(
        cls, account: GoogleAccount, required_capability: GoogleCapability
    ) -> None:
        missing = cls.get_missing_scopes(account, required_capability)
        if missing:
            raise AuthorizationRequiredError(
                capability=required_capability,
                missing_scopes=missing,
                account_id=account.account_id,
            )


class ScopeGuard:
    """Validates that the active Google account possesses the necessary capability."""

    _bypass_for_testing: bool = False

    @classmethod
    def set_bypass_for_testing(cls, bypass: bool = True) -> None:
        cls._bypass_for_testing = bypass

    @classmethod
    def assert_capability(
        cls,
        account_id: str,
        capability: GoogleCapability,
        account: Optional[GoogleAccount] = None,
    ) -> None:
        if cls._bypass_for_testing:
            return

        if account is not None:
            ScopeRegistry.validate_capability(account, capability)
            return

        from jarvis.integrations.google.auth.manager import get_global_auth_manager
        mgr = get_global_auth_manager()
        acc = mgr.get_account(account_id)
        if acc:
            ScopeRegistry.validate_capability(acc, capability)

"""Data models for Google Accounts and Authentication state."""
from __future__ import annotations

import time
from enum import StrEnum
from typing import Set, Tuple
from pydantic import BaseModel, ConfigDict, Field


class AccountStatus(StrEnum):
    READY = "READY"
    CONNECTED = "READY"
    DISCONNECTED = "DISCONNECTED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SCOPE_REQUIRED = "SCOPE_REQUIRED"
    RATE_LIMITED = "RATE_LIMITED"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class GoogleAccount(BaseModel):
    """Represents a connected Google account identity and capability state."""
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(description="Unique identifier, typically hashed email or Google sub ID")
    email: str = Field(description="User primary email address")
    display_label: str = Field(default="primary", description="Human-friendly label: personal, work, college")
    granted_scopes: Set[str] = Field(default_factory=set, description="Set of granted OAuth scope URIs")
    enabled_services: Set[str] = Field(default_factory=set, description="Set of enabled services: gmail, calendar, drive")
    status: AccountStatus = Field(default=AccountStatus.AUTH_REQUIRED)
    created_at: float = Field(default_factory=time.time)
    last_refreshed_at: float = Field(default_factory=time.time)

    def has_scope(self, scope_uri: str) -> bool:
        """Check if specific scope URI is granted."""
        return scope_uri in self.granted_scopes

    def has_all_scopes(self, scope_uris: Set[str] | Tuple[str, ...]) -> bool:
        """Check if all required scope URIs are granted."""
        return set(scope_uris).issubset(self.granted_scopes)


class TokenMetadata(BaseModel):
    """Metadata about stored tokens, excluding the raw secret material."""
    model_config = ConfigDict(extra="forbid")

    account_id: str
    scope_set: Tuple[str, ...] = Field(default_factory=tuple)
    expires_at: float = 0.0
    token_store_ref: str = "keyring"
    health_state: str = "valid"

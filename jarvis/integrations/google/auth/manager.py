"""Google Authentication Manager coordinating OAuth loopback, tokens, and accounts."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

from jarvis.integrations.google.auth.models import AccountStatus, GoogleAccount, TokenMetadata
from jarvis.integrations.google.auth.scopes import (
    AuthorizationRequiredError,
    GoogleCapability,
    ScopeRegistry,
)
from jarvis.integrations.google.auth.token_store import SecureTokenStore

logger = logging.getLogger(__name__)

DEFAULT_CREDENTIALS_DIR = Path.home() / ".jarvis" / "credentials"
DEFAULT_CLIENT_SECRET_FILE = DEFAULT_CREDENTIALS_DIR / "google_client_secret.json"


class GoogleAuthManager:
    """Manages Google OAuth 2.0 lifecycle, multi-account registration, and token refreshes."""

    def __init__(
        self,
        token_store: Optional[SecureTokenStore] = None,
        client_secret_path: Optional[Path | str] = None,
    ) -> None:
        self.token_store = token_store or SecureTokenStore()
        self.client_secret_path = Path(client_secret_path) if client_secret_path else DEFAULT_CLIENT_SECRET_FILE
        self._accounts: Dict[str, GoogleAccount] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
        self._credentials_cache: Dict[str, Any] = {}

    @property
    def has_client_secret(self) -> bool:
        """Check if OAuth client_secret.json file exists on host."""
        return self.client_secret_path.exists() and self.client_secret_path.stat().st_size > 0

    def register_account(self, account: GoogleAccount) -> None:
        """Register or update an account in memory."""
        self._accounts[account.account_id] = account

    def get_account(self, identifier: Optional[str] = None) -> Optional[GoogleAccount]:
        """Retrieve account by ID, email, or display label.
        
        If identifier is None and exactly one account exists, returns that account.
        """
        if not self._accounts:
            return None

        if identifier is None:
            if len(self._accounts) == 1:
                return next(iter(self._accounts.values()))
            # If multiple accounts exist, look for primary/default
            for acc in self._accounts.values():
                if acc.display_label in ("primary", "personal"):
                    return acc
            return next(iter(self._accounts.values()))

        # Direct account_id match
        if identifier in self._accounts:
            return self._accounts[identifier]

        # Email match or label match
        ident_lower = identifier.lower()
        for acc in self._accounts.values():
            if acc.email.lower() == ident_lower or acc.display_label.lower() == ident_lower:
                return acc

        return None

    def list_accounts(self) -> List[GoogleAccount]:
        """Return list of all registered accounts."""
        return list(self._accounts.values())

    async def get_credentials(
        self,
        account_id: Optional[str] = None,
        required_capability: Optional[GoogleCapability] = None,
    ) -> Any:
        """Obtain valid Google OAuth Credentials for an account, refreshing if expired."""
        account = self.get_account(account_id)
        if not account:
            raise RuntimeError(
                f"No connected Google account found matching '{account_id}'. "
                "Run 'python -m jarvis.google connect' to authenticate."
            )

        if account.status == AccountStatus.DISCONNECTED:
            raise RuntimeError(f"Account '{account.email}' is disconnected.")

        # Validate capability scope
        if required_capability:
            ScopeRegistry.validate_capability(account, required_capability)

        # Check cached credentials in memory
        cached = self._credentials_cache.get(account.account_id)
        if cached and getattr(cached, "valid", False) and not getattr(cached, "expired", False):
            return cached

        # Token refresh with per-account concurrency lock
        if account.account_id not in self._refresh_locks:
            self._refresh_locks[account.account_id] = asyncio.Lock()

        async with self._refresh_locks[account.account_id]:
            # Double-check cache after acquiring lock
            cached = self._credentials_cache.get(account.account_id)
            if cached and getattr(cached, "valid", False) and not getattr(cached, "expired", False):
                return cached

            return await self._refresh_token_for_account(account)

    async def _refresh_token_for_account(self, account: GoogleAccount) -> Any:
        """Internal token refresh logic."""
        token_data = self.token_store.get_refresh_token(account.account_id)
        if not token_data or "refresh_token" not in token_data:
            account.status = AccountStatus.AUTH_REQUIRED
            raise RuntimeError(
                f"Missing refresh token for account '{account.email}'. Reauthorization required."
            )

        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            creds = Credentials(
                token=None,  # ephemeral access token
                refresh_token=token_data["refresh_token"],
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=list(account.granted_scopes),
            )

            # Refresh in thread
            def do_refresh():
                creds.refresh(Request())
                return creds

            refreshed_creds = await asyncio.to_thread(do_refresh)
            account.status = AccountStatus.CONNECTED
            account.last_refreshed_at = time.time()
            self._credentials_cache[account.account_id] = refreshed_creds
            logger.info("Successfully refreshed OAuth access token for %s", account.email)
            return refreshed_creds

        except Exception as exc:
            err_str = str(exc).lower()
            if "invalid_grant" in err_str or "expired" in err_str:
                account.status = AccountStatus.AUTH_REQUIRED
                logger.warning("Refresh token expired or revoked for %s: %s", account.email, exc)
            else:
                account.status = AccountStatus.ERROR
            raise RuntimeError(f"Google token refresh failed for '{account.email}': {exc}")

    def disconnect_account(self, account_id: str) -> bool:
        """Disconnect account and purge stored credentials."""
        account = self.get_account(account_id)
        if not account:
            return False

        account.status = AccountStatus.DISCONNECTED
        self.token_store.delete_refresh_token(account.account_id)
        self._credentials_cache.pop(account.account_id, None)
        logger.info("Disconnected Google account %s and purged token", account.email)
        return True


_GLOBAL_AUTH_MANAGER: Optional[GoogleAuthManager] = None


def get_global_auth_manager() -> GoogleAuthManager:
    """Retrieve singleton GoogleAuthManager instance."""
    global _GLOBAL_AUTH_MANAGER
    if _GLOBAL_AUTH_MANAGER is None:
        _GLOBAL_AUTH_MANAGER = GoogleAuthManager()
    return _GLOBAL_AUTH_MANAGER


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
LOCAL_CONFIG_SECRET_FILE = Path("config/google_client_secret.json")
ACCOUNTS_METADATA_FILE = Path("config/google_accounts.json")


class GoogleAuthManager:
    """Manages Google OAuth 2.0 lifecycle, multi-account registration, and token refreshes."""

    def __init__(
        self,
        token_store: Optional[SecureTokenStore] = None,
        client_secret_path: Optional[Path | str] = None,
    ) -> None:
        self.token_store = token_store or SecureTokenStore()
        if client_secret_path:
            self.client_secret_path = Path(client_secret_path)
        elif LOCAL_CONFIG_SECRET_FILE.exists():
            self.client_secret_path = LOCAL_CONFIG_SECRET_FILE
        else:
            self.client_secret_path = DEFAULT_CLIENT_SECRET_FILE

        self._accounts: Dict[str, GoogleAccount] = {}
        self._refresh_locks: Dict[str, asyncio.Lock] = {}
        self._credentials_cache: Dict[str, Any] = {}
        self._load_accounts_metadata()

    @property
    def has_client_secret(self) -> bool:
        """Check if OAuth client_secret.json file exists on host."""
        return self.client_secret_path.exists() and self.client_secret_path.stat().st_size > 0

    def _save_accounts_metadata(self) -> None:
        ACCOUNTS_METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = [acc.model_dump(mode="json") for acc in self._accounts.values()]
        with open(ACCOUNTS_METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _load_accounts_metadata(self) -> None:
        if ACCOUNTS_METADATA_FILE.exists():
            try:
                with open(ACCOUNTS_METADATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        acc = GoogleAccount.model_validate(item)
                        self._accounts[acc.account_id] = acc
            except Exception as e:
                logger.warning("Failed loading Google accounts metadata: %s", e)

    def authorize_capabilities(
        self,
        capabilities: Iterable[GoogleCapability],
        account_id: Optional[str] = None,
        display_label: str = "Personal Google",
    ) -> GoogleAccount:
        """Run desktop loopback OAuth flow and register account."""
        if not self.has_client_secret:
            raise FileNotFoundError(
                f"Google OAuth client secrets file not found at {self.client_secret_path}. "
                "Please place google_client_secret.json in config/ directory."
            )

        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        requested_scopes = set()
        for cap in capabilities:
            scope_uri = ScopeRegistry.get_scope_for_capability(cap)
            if scope_uri:
                requested_scopes.add(scope_uri)
        requested_scopes.add("https://www.googleapis.com/auth/userinfo.email")
        requested_scopes.add("openid")

        with open(self.client_secret_path, "r", encoding="utf-8") as f:
            secret_data = json.load(f)

        client_info = secret_data.get("installed") or secret_data.get("web")
        if not client_info:
            raise ValueError("Invalid google_client_secret.json: missing 'installed' or 'web' key")

        flow_config = {"installed": client_info}
        flow = InstalledAppFlow.from_client_config(
            flow_config,
            scopes=sorted(list(requested_scopes)),
        )

        creds = flow.run_local_server(
            host="127.0.0.1",
            port=8080,
            authorization_prompt_message="Opening browser for Google authorization...",
            success_message="Google authorization successful! You can now close this browser window.",
            open_browser=True,
        )

        email = "user@gmail.com"
        try:
            oauth2_service = build("oauth2", "v2", credentials=creds)
            user_info = oauth2_service.userinfo().get().execute()
            email = user_info.get("email", email)
        except Exception as e:
            logger.warning("Could not fetch userinfo email: %s", e)

        acc_id = account_id or f"google_{email.replace('@', '_').replace('.', '_')}"

        if creds.refresh_token:
            self.token_store.store_refresh_token(
                account_id=acc_id,
                refresh_token=creds.refresh_token,
                client_id=client_info.get("client_id"),
                client_secret=client_info.get("client_secret"),
                token_uri=client_info.get("token_uri", "https://oauth2.googleapis.com/token"),
            )

        enabled_services = set()
        for cap in capabilities:
            cap_val = cap.value if hasattr(cap, "value") else str(cap)
            if "gmail" in cap_val.lower():
                enabled_services.add("gmail")
            elif "calendar" in cap_val.lower():
                enabled_services.add("calendar")
            elif "drive" in cap_val.lower():
                enabled_services.add("drive")

        account = GoogleAccount(
            account_id=acc_id,
            email=email,
            display_label=display_label,
            granted_scopes=set(creds.scopes or requested_scopes),
            enabled_services=enabled_services,
            status=AccountStatus.READY,
        )

        self.register_account(account)
        self._credentials_cache[acc_id] = creds
        self._save_accounts_metadata()
        logger.info("Successfully connected Google account %s (%s)", acc_id, email)
        return account

    def register_account(self, account: GoogleAccount) -> None:
        """Register or update an account in memory."""
        self._accounts[account.account_id] = account
        self._save_accounts_metadata()

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


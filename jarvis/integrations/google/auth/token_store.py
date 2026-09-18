"""Secure token storage using Windows Credential Manager / keyring with safe fallback."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)

KEYRING_SERVICE_NAME = "jarvis_edge_google_oauth"


class SecureTokenStore:
    """Manages secure storage of OAuth refresh token material.
    
    Prefers Windows Credential Manager via the `keyring` library.
    Falls back to an in-memory secure vault for headless CI or environments
    without accessible credential managers.
    """

    def __init__(self, use_keyring: bool = True) -> None:
        self._use_keyring = use_keyring
        self._memory_vault: Dict[str, str] = {}

    def save_refresh_token(self, account_id: str, token_data: Union[str, Dict[str, Any]]) -> bool:
        """Securely store refresh token data for an account ID."""
        if not account_id or not token_data:
            return False

        if isinstance(token_data, dict):
            serialized = json.dumps(token_data)
        else:
            serialized = str(token_data)

        if self._use_keyring:
            try:
                import keyring
                keyring.set_password(KEYRING_SERVICE_NAME, account_id, serialized)
                logger.info("Saved OAuth refresh token to OS keyring for account %s", account_id)
                return True
            except Exception as exc:
                logger.warning(
                    "OS keyring unavailable for account %s (%s); storing in memory vault",
                    account_id,
                    exc,
                )

        self._memory_vault[account_id] = serialized
        return True

    def get_refresh_token(self, account_id: str) -> Optional[Union[str, Dict[str, Any]]]:
        """Retrieve stored refresh token data for an account ID."""
        if not account_id:
            return None

        raw: Optional[str] = None

        if self._use_keyring:
            try:
                import keyring
                raw = keyring.get_password(KEYRING_SERVICE_NAME, account_id)
            except Exception as exc:
                logger.debug("Keyring get failed for %s: %s", account_id, exc)

        if not raw:
            raw = self._memory_vault.get(account_id)

        if not raw:
            return None

        try:
            return json.loads(raw)
        except Exception:
            return raw

    def has_refresh_token(self, account_id: str) -> bool:
        """Check if a refresh token exists for the account."""
        return self.get_refresh_token(account_id) is not None

    def delete_refresh_token(self, account_id: str) -> bool:
        """Delete stored refresh token material for an account ID."""
        deleted = False

        if self._use_keyring:
            try:
                import keyring
                keyring.delete_password(KEYRING_SERVICE_NAME, account_id)
                deleted = True
            except Exception:
                pass

        if account_id in self._memory_vault:
            del self._memory_vault[account_id]
            deleted = True

        return deleted

    def clear(self) -> None:
        """Clear the in-memory vault."""
        self._memory_vault.clear()

    def __repr__(self) -> str:
        return f"<SecureTokenStore use_keyring={self._use_keyring} memory_accounts={len(self._memory_vault)}>"

"""At-rest encryption for stored conversation examples and style profiles.

Follows the existing JARVIS pattern (Google tokens): the secret lives in the OS credential store
(Windows Credential Manager via ``keyring``) and the data is encrypted with Fernet (AES-128-CBC + HMAC).
When the credential store or ``cryptography`` is unavailable, data is stored as plain text and the
UI reports ``encryption: unavailable`` instead of pretending otherwise.
"""
from __future__ import annotations

import base64
import logging
from typing import Optional

logger = logging.getLogger("jarvis.whatsapp.personal_reply.crypto")

KEYRING_SERVICE = "jarvis_edge_whatsapp_personal"
KEYRING_USER = "data_key"
_PREFIX = "enc1:"


class DataBox:
    def __init__(self, key: Optional[bytes] = None, use_keyring: bool = True) -> None:
        self._fernet = None
        self.status = "unavailable"
        try:
            from cryptography.fernet import Fernet
        except Exception:
            return
        if key is None and use_keyring:
            key = self._keyring_key(Fernet)
        if key is not None:
            try:
                self._fernet = Fernet(key)
                self.status = "keyring" if use_keyring else "provided-key"
            except Exception as exc:
                logger.warning("Invalid WhatsApp data key: %s", exc)

    @staticmethod
    def _keyring_key(fernet_cls) -> Optional[bytes]:
        try:
            import keyring
            stored = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
            if stored:
                return stored.encode()
            new_key = fernet_cls.generate_key()
            keyring.set_password(KEYRING_SERVICE, KEYRING_USER, new_key.decode())
            return new_key
        except Exception as exc:  # no OS credential store (headless / CI)
            logger.info("OS credential store unavailable; WhatsApp style data stored unencrypted (%s)", exc)
            return None

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, text: str) -> str:
        if not text or self._fernet is None:
            return text or ""
        return _PREFIX + self._fernet.encrypt(text.encode("utf-8")).decode("ascii")

    def decrypt(self, blob: str) -> str:
        if not blob or not blob.startswith(_PREFIX):
            return blob or ""
        if self._fernet is None:
            return ""  # encrypted with a key we no longer have: never return ciphertext as text
        try:
            return self._fernet.decrypt(blob[len(_PREFIX):].encode("ascii")).decode("utf-8")
        except Exception:
            return ""


def test_key() -> bytes:
    """Deterministic key for tests only."""
    return base64.urlsafe_b64encode(b"jarvis-test-key-0123456789abcdef"[:32])

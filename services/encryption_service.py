"""Encryption service for sensitive settings at rest."""
from __future__ import annotations

import os
import base64
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class EncryptionService:
    """Encrypts/decrypts sensitive settings using Fernet symmetric encryption."""

    _SALT = b"operion_smtp_salt_v1"  # Application salt

    def __init__(self, master_key: str | None = None):
        self._master_key = master_key or os.environ.get("OPERION_ENCRYPTION_KEY", "")
        if not self._master_key:
            logger.warning("OPERION_ENCRYPTION_KEY not set — encryption disabled, using plaintext fallback")
        self._fernet = None
        if self._master_key:
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=self._SALT, iterations=100000)
            key = base64.urlsafe_b64encode(kdf.derive(self._master_key.encode()))
            self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        if not self._fernet:
            return plaintext  # No encryption key configured
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        if not self._fernet:
            return ciphertext  # No encryption key configured
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception:
            logger.warning("Failed to decrypt — returning ciphertext (possibly legacy plaintext)")
            return ciphertext


_encryption = EncryptionService()


def encrypt_value(value: str) -> str:
    return _encryption.encrypt(value)


def decrypt_value(value: str) -> str:
    return _encryption.decrypt(value)

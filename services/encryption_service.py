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
        """Decrypt a Fernet-encrypted value.

        If the value doesn't look like Fernet ciphertext (legacy plaintext),
        it is returned as-is and optionally re-encrypted for future reads.
        """
        if not self._fernet:
            return ciphertext  # No encryption key configured
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except Exception:
            # Detect legacy plaintext: Fernet tokens are base64-encoded
            # and always start with 'gAAAAA'. If the value doesn't match
            # this pattern, it was likely stored before encryption was added.
            if not self._looks_encrypted(ciphertext):
                logger.debug(
                    "Value appears to be legacy plaintext — returning as-is "
                    "(will be encrypted on next write)"
                )
                return ciphertext
            logger.warning(
                "Failed to decrypt Fernet ciphertext — data may be corrupt "
                "or encrypted with a different key"
            )
            return ciphertext

    @staticmethod
    def _looks_encrypted(value: str) -> bool:
        """Heuristic: Fernet tokens are URL-safe base64 with a version prefix.

        Every Fernet token starts with ``g`` (the base64url of the version
        byte 0x80) and is at least 100 characters long (version + 8-byte
        timestamp + 16-byte IV + minimum 16-byte ciphertext + 32-byte HMAC
        -> base64url). Requiring that prefix and minimum length, in addition
        to a clean base64url decode (padding restored on the fly for any
        unpadded variant), keeps the heuristic from treating ordinary legacy
        plaintext as encrypted. It only gates the corrupt-data warning path:
        ``fernet.decrypt()`` always runs first and plaintext is returned
        unchanged either way.
        """
        candidate = (value or "").strip()
        if not candidate.startswith("g") or len(candidate) < 100:
            return False
        try:
            base64.urlsafe_b64decode(
                candidate.encode() + b"=" * (-len(candidate) % 4)
            )
            return True
        except Exception:
            return False


_encryption = EncryptionService()


def encrypt_value(value: str) -> str:
    return _encryption.encrypt(value)


def decrypt_value(value: str) -> str:
    return _encryption.decrypt(value)

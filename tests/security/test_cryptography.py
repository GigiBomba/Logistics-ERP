"""Tests for cryptographic properties: bcrypt salt uniqueness, JWT algorithm pinning, signature tamper detection."""

import os
import re

import bcrypt
import jwt as pyjwt
import pytest
from jwt.exceptions import PyJWTError

from backend.config import BackendSettings
from backend.security import decode_access_token, hash_password

# Ensure a JWT secret key is available when tests run standalone
# (the conftest's session-level ``app`` fixture also sets this,
# but for isolated runs we provide it here).
_JWT_TEST_SECRET = "test-secret-key-32-chars-for-testing-only!!"
os.environ.setdefault("OPERION_JWT_SECRET_KEY", _JWT_TEST_SECRET)


class TestBcryptCryptography:
    """Bcrypt hashing properties."""

    def test_bcrypt_salt_uniqueness(self):
        """Generate 10 hashes, verify all have different salts."""
        salts = set()
        for _ in range(10):
            h = hash_password("test_password", rounds=4)
            # Extract the salt from the bcrypt hash (format: $2b$XX$22-char-salt + hash)
            # The salt is the first 22 characters after the second $
            salt = h[:29]  # "$2b$XX$" (7 chars) + 22 chars of salt = 29 chars
            salts.add(salt)
        assert len(salts) == 10, f"Expected 10 unique salts, got {len(salts)}"

    def test_bcrypt_hash_format(self):
        """Verify hash starts with $2b$ and has correct format."""
        h = hash_password("test_password", rounds=4)
        assert h.startswith("$2b$"), f"Hash should start with $2b$, got: {h[:7]}"
        # Format: $2b$<rounds>$<53-char-base64-string>
        assert re.match(r"^\$2b\$\d{2}\$[A-Za-z0-9./]{53}$", h), (
            f"Hash does not match expected bcrypt format: {h}"
        )
        assert len(h) == 60, f"Bcrypt hash should be 60 characters, got {len(h)}"


class TestJWTCryptography:
    """JWT algorithm pinning, none-alg rejection, signature tampering."""

    def test_jwt_algorithm_pinned(self):
        """Verify decode_access_token uses algorithms=[HS256], not trusting header."""
        settings = BackendSettings()
        # Create a token signed with HS512 (different algorithm)
        token = pyjwt.encode(
            {"sub": "test@test.com", "role": "admin"},
            settings.jwt_secret_key,
            algorithm="HS512",
        )
        # decode_access_token should still require HS256 and reject this
        with pytest.raises(PyJWTError):
            decode_access_token(token)

    def test_pyjwt_rejects_none_alg(self):
        """Use PyJWT directly with alg=None on a token, verify decode rejects it."""
        settings = BackendSettings()

        # Manually craft a token with algorithm "none" (just base64 encode)
        import json
        import base64

        header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
        payload = base64.urlsafe_b64encode(json.dumps({"sub": "test", "role": "admin"}).encode()).rstrip(b"=").decode()
        none_token = f"{header}.{payload}."

        # PyJWT with algorithms=["HS256"] should reject alg=none
        with pytest.raises(PyJWTError):
            pyjwt.decode(none_token, settings.jwt_secret_key, algorithms=["HS256"])

        # Also verify our decode_access_token rejects it
        with pytest.raises(PyJWTError):
            decode_access_token(none_token)

    def test_jwt_signature_tamper_detected(self):
        """Modify any byte in signature, verify decode raises."""
        settings = BackendSettings()
        token = pyjwt.encode(
            {"sub": "test@test.com", "role": "admin"},
            settings.jwt_secret_key,
            algorithm=settings.jwt_algorithm,
        )

        # Split the token into parts and corrupt the signature
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

        # Flip a bit in the signature
        corrupted_sig = list(parts[2])
        corrupted_sig[0] = chr(ord(corrupted_sig[0]) ^ 0x01) if corrupted_sig[0] else "a"
        parts[2] = "".join(corrupted_sig)
        tampered_token = ".".join(parts)

        with pytest.raises(PyJWTError):
            decode_access_token(tampered_token)


class TestSecretKey:
    """Secret key strength properties."""

    def test_secret_key_minimum_length(self):
        """Verify the test secret key is at least 32 characters."""
        settings = BackendSettings()
        assert len(settings.jwt_secret_key) >= 32, (
            f"JWT secret key is only {len(settings.jwt_secret_key)} chars "
            f"(minimum 32 required)"
        )

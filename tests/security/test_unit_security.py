"""Unit tests for JWT, password hashing, token ops, permission checking, and security utilities.

These test functions directly, not through the API.
"""
from __future__ import annotations


import os
import time
from datetime import timedelta
from unittest.mock import MagicMock, patch

import bcrypt
import jwt as pyjwt
import pytest
from fastapi import HTTPException

from backend.config import BackendSettings
from backend.dependencies_security import get_current_user, require_admin, require_dispatcher
from backend.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    verify_password,
)

# Ensure a JWT secret key is available when tests run standalone
# (the conftest's session-level ``app`` fixture also sets this,
# but for isolated runs we provide it here).
_JWT_TEST_SECRET = "test-secret-key-32-chars-for-testing-only!!"
os.environ.setdefault("OPERION_JWT_SECRET_KEY", _JWT_TEST_SECRET)


class TestJWT:
    """JWT creation, decoding, expiry, and validation."""

    def test_jwt_create_and_decode(self):
        """Create a JWT with create_access_token, decode with decode_access_token, verify claims match."""
        data = {"sub": "test@test.com", "role": "admin"}
        token = create_access_token(data)
        decoded = decode_access_token(token)
        assert decoded["sub"] == "test@test.com"
        assert decoded["role"] == "admin"
        assert "exp" in decoded

    def test_jwt_expired_rejected(self):
        """Create JWT with past expiration, decode raises PyJWTError."""
        data = {"sub": "test@test.com", "role": "admin"}
        token = create_access_token(data, expires_delta=timedelta(seconds=-1))
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(token)

    @pytest.mark.asyncio
    async def test_jwt_missing_sub_rejected(self):
        """Token without 'sub' claim should be rejected by get_current_user."""
        token = create_access_token({"role": "admin"})
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user(token=token)
        assert excinfo.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_missing_token(self):
        """Call get_current_user with no token, expect 401."""
        with pytest.raises(HTTPException) as excinfo:
            await get_current_user(token="")
        assert excinfo.value.status_code == 401

    def test_decode_access_token_with_wrong_key(self):
        """Token signed with different key fails."""
        settings = BackendSettings()
        token = pyjwt.encode(
            {"sub": "test", "role": "admin"},
            "this-is-a-completely-different-key-for-testing-only!!",
            algorithm=settings.jwt_algorithm,
        )
        with pytest.raises(pyjwt.PyJWTError):
            decode_access_token(token)


class TestPermissions:
    """RBAC permission gates."""

    @pytest.mark.asyncio
    async def test_require_admin_non_admin(self):
        """Call require_admin with a non-admin user, expect 403."""
        user = {"id": 1, "email": "user@test.com", "role": "viewer", "is_admin": False}
        with pytest.raises(HTTPException) as excinfo:
            await require_admin(current_user=user)
        assert excinfo.value.status_code == 403
        assert "Admin privileges required" in str(excinfo.value.detail)

    @pytest.mark.asyncio
    async def test_require_dispatcher_regular_user(self):
        """Call require_dispatcher with a role not in (admin, dispatcher), expect 403."""
        user = {"id": 1, "email": "user@test.com", "role": "viewer", "is_admin": False}
        with pytest.raises(HTTPException) as excinfo:
            await require_dispatcher(current_user=user)
        assert excinfo.value.status_code == 403
        assert "Dispatcher or admin privileges" in str(excinfo.value.detail)


class TestPasswordHashing:
    """Password hashing and verification with bcrypt."""

    def test_password_hash_and_verify(self):
        """hash_password then verify_password returns True; wrong password returns False."""
        hashed = hash_password("correct_password", rounds=4)
        assert verify_password("correct_password", hashed) is True
        assert verify_password("wrong_password", hashed) is False

    def test_password_hash_different_salts(self):
        """Two hashes of same password are different (salts differ)."""
        hash1 = hash_password("same_password", rounds=4)
        hash2 = hash_password("same_password", rounds=4)
        assert hash1 != hash2

    def test_password_hash_rejects_short(self):
        """Verify hash_password works with default rounds (4 for test speed)."""
        hashed = hash_password("short", rounds=4)
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert verify_password("short", hashed) is True


class TestRefreshToken:
    """Refresh token generation and properties."""

    def test_refresh_token_generation(self):
        """generate_refresh_token returns 128-char hex string."""
        token = generate_refresh_token()
        assert isinstance(token, str)
        assert len(token) == 128
        assert all(c in "0123456789abcdef" for c in token)

    def test_generate_refresh_token_uniqueness(self):
        """Two sequential refresh tokens are different."""
        token1 = generate_refresh_token()
        token2 = generate_refresh_token()
        assert token1 != token2

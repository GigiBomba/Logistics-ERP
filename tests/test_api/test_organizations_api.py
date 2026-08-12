"""Tests for organization API endpoints."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


class TestOrganizationsUnauthenticated:
    """Tests for organization endpoints without authentication — all return 401."""

    BASE = "/api/v1/organizations"

    def test_list_orgs_requires_auth(self, app):
        """GET /api/v1/organizations returns 401 without auth."""
        client = TestClient(app)
        resp = client.get(f"{self.BASE}")
        assert resp.status_code == 401

    def test_get_org_requires_auth(self, app):
        """GET /api/v1/organizations/{slug} returns 401 without auth."""
        client = TestClient(app)
        resp = client.get(f"{self.BASE}/test-org")
        assert resp.status_code == 401

    def test_create_requires_auth(self, app):
        """POST /api/v1/organizations returns 401 without auth."""
        client = TestClient(app)
        resp = client.post(f"{self.BASE}", json={"name": "Test Org"})
        assert resp.status_code == 401

    def test_update_requires_auth(self, app):
        """PATCH /api/v1/organizations/{slug} returns 401 without auth."""
        client = TestClient(app)
        resp = client.patch(f"{self.BASE}/test-org", json={"name": "New"})
        assert resp.status_code == 401

    def test_list_members_requires_auth(self, app):
        """GET /api/v1/organizations/{slug}/members returns 401 without auth."""
        client = TestClient(app)
        resp = client.get(f"{self.BASE}/test-org/members")
        assert resp.status_code == 401

    def test_invite_requires_auth(self, app):
        """POST /api/v1/organizations/{slug}/invitations returns 401 without auth."""
        client = TestClient(app)
        resp = client.post(
            f"{self.BASE}/test-org/invitations",
            json={"email": "test@company.com"},
        )
        assert resp.status_code == 401

    def test_remove_member_requires_auth(self, app):
        """DELETE /api/v1/organizations/{slug}/members/{id} returns 401 without auth."""
        client = TestClient(app)
        resp = client.delete(f"{self.BASE}/test-org/members/1")
        assert resp.status_code == 401

    def test_list_invitations_requires_auth(self, app):
        """GET /api/v1/organizations/{slug}/invitations returns 401 without auth."""
        client = TestClient(app)
        resp = client.get(f"{self.BASE}/test-org/invitations")
        assert resp.status_code == 401

    def test_accept_invitation_requires_auth(self, app):
        """POST /api/v1/organizations/invitations/{token}/accept returns 401 without auth."""
        client = TestClient(app)
        resp = client.post(f"{self.BASE}/invitations/token/accept")
        assert resp.status_code == 401


class TestOrganizationsAuthenticated:
    """Tests for organization endpoints with authentication.

    Uses ``client_with_mocks`` so that the ``db`` dependency is mocked and
    we can control what the database returns.
    """

    BASE = "/api/v1/organizations"

    def test_get_nonexistent_org_returns_404(self, client_with_mocks):
        """GET /api/v1/organizations/non-existent returns 404 even with valid auth."""
        client, mocks = client_with_mocks

        # _get_org_by_slug calls db.execute().fetchone()
        not_found = MagicMock()
        not_found.fetchone.return_value = None
        mocks["db"].execute.return_value = not_found

        resp = client.get(f"{self.BASE}/non-existent")
        assert resp.status_code == 404

    def _stub_invitation_row(self, mocks, row):
        """Stub the accept endpoint's invitation SELECT to return ``row``."""
        stub = MagicMock()
        stub.fetchone.return_value = row
        mocks["db"].execute.return_value = stub

    def test_accept_invitation_unknown_token_returns_404_invalid(self, client_with_mocks):
        """Unknown token → 404 with ``invitation/invalid``."""
        client, mocks = client_with_mocks
        self._stub_invitation_row(mocks, None)

        resp = client.post(f"{self.BASE}/invitations/unknown-token/accept")
        assert resp.status_code == 404
        body = resp.json()
        # Bare test app uses Starlette's default HTTPException handler, so the
        # error_code lives at body["detail"]["error_code"] (see test_auth_e2e.py).
        assert body["detail"]["error_code"] == "invitation/invalid"

    def test_accept_invitation_rate_limited_after_10_attempts(self, client_with_mocks):
        """More than 10 accept attempts per IP within 10 min → 429."""
        from backend.utils.rate_limit import _fallback

        _fallback.clear()
        try:
            client, mocks = client_with_mocks
            # No invitation matches — the limiter runs before the lookup, so
            # each attempt must reach the (mocked) DB and 404.
            self._stub_invitation_row(mocks, None)
            for _ in range(10):
                resp = client.post(f"{self.BASE}/invitations/unknown-token/accept")
                assert resp.status_code == 404  # limiter passes, token unknown
            resp = client.post(f"{self.BASE}/invitations/unknown-token/accept")
            assert resp.status_code == 429
        finally:
            _fallback.clear()

    def test_accept_invitation_expired_returns_400_expired(self, client_with_mocks):
        """Invitation already expired (status) → 400 with ``invitation/expired``."""
        client, mocks = client_with_mocks
        self._stub_invitation_row(
            mocks,
            {
                "id": 1,
                "org_id": 1,
                "email": "test@test.com",
                "role": "member",
                "token": "tok-expired",
                "invited_by": 1,
                "status": "expired",
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": "2026-01-02T00:00:00Z",
            },
        )

        resp = client.post(f"{self.BASE}/invitations/tok-expired/accept")
        assert resp.status_code == 400
        body = resp.json()
        assert body["detail"]["error_code"] == "invitation/expired"

    def test_accept_invitation_already_accepted_returns_409(self, client_with_mocks):
        """Invitation already accepted (status) → 409 with ``invitation/already-accepted``."""
        client, mocks = client_with_mocks
        self._stub_invitation_row(
            mocks,
            {
                "id": 2,
                "org_id": 1,
                "email": "test@test.com",
                "role": "member",
                "token": "tok-accepted",
                "invited_by": 1,
                "status": "accepted",
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": "2026-08-01T00:00:00Z",
            },
        )

        resp = client.post(f"{self.BASE}/invitations/tok-accepted/accept")
        assert resp.status_code == 409
        body = resp.json()
        assert body["detail"]["error_code"] == "invitation/already-accepted"

    def test_accept_invitation_email_mismatch_returns_403(self, client_with_mocks):
        """Invitation for a different email → 403 with ``auth/insufficient-permissions``."""
        client, mocks = client_with_mocks
        self._stub_invitation_row(
            mocks,
            {
                "id": 3,
                "org_id": 1,
                "email": "someone-else@test.com",
                "role": "member",
                "token": "tok-mismatch",
                "invited_by": 1,
                "status": "pending",
                "created_at": "2026-01-01T00:00:00Z",
                "expires_at": "2026-08-01T00:00:00Z",
            },
        )

        resp = client.post(f"{self.BASE}/invitations/tok-mismatch/accept")
        assert resp.status_code == 403
        body = resp.json()
        assert body["detail"]["error_code"] == "auth/insufficient-permissions"

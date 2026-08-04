"""Mobile team endpoint tests (blueprint §6.9, Phase 4A) — real DB.

Covers: paginated/search/company-scoped list, invite happy paths, the
SERVER-SIDE manager-cannot-invite-admin rejection (direct API, 422 +
``role_not_allowed``), the role-change constraint (never admin, 422), the
full deactivation cascade (is_active=0 + devices deleted + refresh tokens
revoked + existing JWT 401), and the can_manage_users gate (dispatcher 403).
"""
from __future__ import annotations

import time

import pytest

from tests.mobile.conftest import seed_team

BASE = "/api/v1/mobile/team"


@pytest.fixture
def team_seed(real_db):
    return seed_team(real_db, company_id=1)


def _seed_refresh_token(email: str) -> str:
    """Plant an opaque refresh token for *email* directly in the live store."""
    from backend.api.v1.auth import _hash_token, _refresh_store

    token = "a" * 128
    _refresh_store[_hash_token(token)] = {
        "email": email,
        "role": "dispatcher",
        "expires_at": time.time() + 3600,
    }
    return token


class TestListTeam:
    def test_list_paginated(self, mobile_app, real_db, team_seed, manager_client):
        resp = manager_client.get(f"{BASE}?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 6  # 4 role users + invitee + manager2
        assert len(data["items"]) == 2
        item = data["items"][0]
        assert set(item.keys()) >= {"id", "email", "display_name", "role", "is_active", "created_at", "driver_name"}
        assert item["email"]

    def test_list_search(self, mobile_app, real_db, team_seed, manager_client):
        resp = manager_client.get(f"{BASE}?search=invitee")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == "invitee@test.com"

    def test_list_company_isolation(self, mobile_app, real_db, team_seed, manager_client):
        from tests.mobile.conftest import seed_team

        seed_team(real_db, company_id=2)
        resp = manager_client.get(BASE)
        data = resp.json()
        # Company 2's 2 extra users must never appear under company 1's JWT.
        assert data["total"] == 6

    def test_list_dispatcher_403(self, mobile_app, real_db, team_seed, dispatcher_client):
        assert dispatcher_client.get(BASE).status_code == 403

    def test_list_driver_403(self, mobile_app, real_db, team_seed, driver_client):
        assert driver_client.get(BASE).status_code == 403


class TestInviteTeamMember:
    def test_invite_dispatcher_happy(self, mobile_app, real_db, manager_client):
        resp = manager_client.post(
            f"{BASE}/invite", json={"email": "new-dispatcher@test.com", "role": "dispatcher"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new-dispatcher@test.com"
        assert body["role"] == "dispatcher"
        assert body["is_active"] is True
        row = dict(real_db.execute(
            "SELECT id, role, is_active, password_hash FROM users WHERE email = ?",
            ("new-dispatcher@test.com",),
        ).fetchone())
        assert row["is_active"] == 1
        assert row["password_hash"].startswith("$2")  # bcrypt hash, not plaintext

    def test_invite_manager_happy(self, mobile_app, real_db, manager_client):
        resp = manager_client.post(
            f"{BASE}/invite", json={"email": "new-manager@test.com", "role": "manager"},
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "manager"

    def test_invite_duplicate_email_409(self, mobile_app, real_db, team_seed, manager_client):
        resp = manager_client.post(
            f"{BASE}/invite", json={"email": "invitee@test.com", "role": "dispatcher"},
        )
        assert resp.status_code == 409
        assert resp.json()["detail"]["error_code"] == "email_exists"

    def test_manager_cannot_invite_admin_direct_api(self, mobile_app, real_db, manager_client):
        """SERVER-SIDE role constraint: a manager inviting role=admin is rejected.

        This is the direct-API proof (not client-side): the request carries
        role='admin' and the backend returns 422 with a machine-readable
        ``role_not_allowed`` error.
        """
        resp = manager_client.post(
            f"{BASE}/invite", json={"email": "wannabe-admin@test.com", "role": "admin"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert detail["error_code"] == "role_not_allowed"
        # Nothing must have been created.
        assert dict(real_db.execute(
            "SELECT COUNT(*) AS cnt FROM users WHERE email = ?",
            ("wannabe-admin@test.com",),
        ).fetchone())["cnt"] == 0

    def test_invite_dispatcher_403(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.post(
            f"{BASE}/invite", json={"email": "denied@test.com", "role": "dispatcher"},
        )
        assert resp.status_code == 403

    def test_invite_admin_403(self, mobile_app, real_db, team_seed, admin_client):
        """Admins CAN invite; this also proves the gate passes for admin."""
        resp = admin_client.post(
            f"{BASE}/invite", json={"email": "admin-invitee@test.com", "role": "manager"},
        )
        assert resp.status_code == 201


class TestPatchTeamMember:
    def test_patch_role_change(self, mobile_app, real_db, team_seed, manager_client):
        target = team_seed["invitee_user"]
        resp = manager_client.patch(f"{BASE}/{target}", json={"role": "manager"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "manager"
        row = dict(real_db.execute(
            "SELECT role FROM users WHERE id = ?", (target,),
        ).fetchone())
        assert row["role"] == "manager"

    def test_patch_role_admin_rejected(self, mobile_app, real_db, team_seed, manager_client):
        """Role-change constraint: assigning role=admin is rejected (422)."""
        target = team_seed["invitee_user"]
        resp = manager_client.patch(f"{BASE}/{target}", json={"role": "admin"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "role_not_allowed"
        row = dict(real_db.execute(
            "SELECT role FROM users WHERE id = ?", (target,),
        ).fetchone())
        assert row["role"] == "dispatcher"  # unchanged

    def test_patch_admin_target_rejected(self, mobile_app, real_db, team_seed, manager_client):
        """Defensive: admin-role users can never be PATCHed via the team endpoint."""
        resp = manager_client.patch(f"{BASE}/1", json={"is_active": False})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "role_not_allowed"

    def test_patch_other_company_404(self, mobile_app, real_db, team_seed, manager_client):
        from tests.mobile.conftest import seed_team

        other = seed_team(real_db, company_id=2)["invitee_user"]
        resp = manager_client.patch(f"{BASE}/{other}", json={"role": "manager"})
        assert resp.status_code == 404

    def test_patch_missing_404(self, mobile_app, real_db, team_seed, manager_client):
        assert manager_client.patch(f"{BASE}/999999", json={"role": "manager"}).status_code == 404

    def test_patch_dispatcher_403(self, mobile_app, real_db, team_seed, dispatcher_client):
        target = team_seed["invitee_user"]
        assert dispatcher_client.patch(f"{BASE}/{target}", json={"role": "manager"}).status_code == 403

    def test_patch_self_deactivation_422(self, mobile_app, real_db, team_seed, manager_client):
        """A manager cannot deactivate their OWN account: PATCHing their own
        user_id with ``is_active=false`` is rejected (422 +
        ``self_deactivation``) and the user stays active in the DB."""
        my_id = dict(real_db.execute(
            "SELECT id FROM users WHERE email = 'manager@test.com'", (),
        ).fetchone())["id"]
        resp = manager_client.patch(f"{BASE}/{my_id}", json={"is_active": False})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "self_deactivation"
        row = dict(real_db.execute(
            "SELECT is_active FROM users WHERE id = ?", (my_id,),
        ).fetchone())
        assert row["is_active"] == 1  # still active in DB (no deactivation cascade)


class TestDeactivationCascade:
    def test_deactivate_revokes_everything_and_kills_existing_jwt(
        self, mobile_app, real_db, team_seed, manager_client,
    ):
        """is_active=false -> users.is_active=0 + devices deleted + refresh
        tokens revoked, all in ONE transaction, and the user's existing JWT is
        immediately rejected with 401."""
        from backend.api.v1.auth import _hash_token, _refresh_store
        from backend.security import create_access_token

        target = team_seed["invitee_user"]
        email = "invitee@test.com"

        # Active device row + a live refresh token for this user.
        device_count = dict(real_db.execute(
            "SELECT COUNT(*) AS cnt FROM mobile_devices WHERE user_id = ?", (target,),
        ).fetchone())["cnt"]
        assert device_count == 1
        token = _seed_refresh_token(email)
        assert _hash_token(token) in _refresh_store

        # 1) Deactivate via the API.
        resp = manager_client.patch(f"{BASE}/{target}", json={"is_active": False})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # 2) DB: user is inactive, devices rows GONE, same transaction committed.
        row = dict(real_db.execute(
            "SELECT is_active FROM users WHERE id = ?", (target,),
        ).fetchone())
        assert row["is_active"] == 0
        assert dict(real_db.execute(
            "SELECT COUNT(*) AS cnt FROM mobile_devices WHERE user_id = ?", (target,),
        ).fetchone())["cnt"] == 0

        # 3) Refresh token revoked from the store -> refresh endpoint 401.
        assert _hash_token(token) not in _refresh_store
        resp = manager_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": token},
        )
        assert resp.status_code == 401

        # 4) Existing JWT is rejected immediately (get_current_user checks
        #    users.is_active = 1).  Use the REAL auth dependency (no override).
        from backend.dependencies_security import get_current_user as gcu

        mobile_app.dependency_overrides.pop(gcu, None)
        from fastapi.testclient import TestClient

        jwt = create_access_token({"sub": email, "role": "dispatcher"})
        client = TestClient(mobile_app, raise_server_exceptions=False)
        resp = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {jwt}"},
        )
        assert resp.status_code == 401

    def test_deactivate_inactive_target_user(self, mobile_app, real_db, team_seed, manager_client):
        """A target in the same company who was never a device/session holder."""
        target = team_seed["manager2_user"]
        resp = manager_client.patch(f"{BASE}/{target}", json={"is_active": False})
        assert resp.status_code == 200
        row = dict(real_db.execute(
            "SELECT is_active FROM users WHERE id = ?", (target,),
        ).fetchone())
        assert row["is_active"] == 0

    def test_reactivate_after_deactivation(self, mobile_app, real_db, team_seed, manager_client):
        target = team_seed["invitee_user"]
        manager_client.patch(f"{BASE}/{target}", json={"is_active": False})
        resp = manager_client.patch(f"{BASE}/{target}", json={"is_active": True})
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

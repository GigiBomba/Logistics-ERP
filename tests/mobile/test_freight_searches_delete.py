"""Freight saved-search DELETE tests (Gate-29 A2).

Covers ``DELETE /api/v1/freight/searches/{search_id}`` on a REAL DB:
owner delete (200 + row gone) and foreign user/company (404 + row kept).
The dispatcher test user is company 1 / user id 2 (tests/mobile/conftest).
"""
from __future__ import annotations

BASE = "/api/v1/freight/searches"


def _seed_search(db, search_id: str, company_id: int, user_id: int, label: str = "Saved") -> None:
    db.execute(
        "INSERT INTO saved_searches (id, company_id, user_id, label, filters, created_at) "
        "VALUES (?, ?, ?, ?, '{}', '2026-07-01T00:00:00Z')",
        (search_id, company_id, user_id, label),
    )
    db.conn.commit()


def _count(db, search_id: str) -> int:
    row = db.execute(
        "SELECT COUNT(*) AS cnt FROM saved_searches WHERE id = ?", (search_id,)
    ).fetchone()
    return dict(row)["cnt"]


class TestDeleteSavedSearch:
    def test_owner_delete_200_and_row_gone(self, mobile_app, real_db, dispatcher_client):
        _seed_search(real_db, "ss-owner", company_id=1, user_id=2)

        resp = dispatcher_client.delete(f"{BASE}/ss-owner")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"status": "deleted"}
        assert _count(real_db, "ss-owner") == 0

    def test_foreign_company_404_and_row_kept(self, mobile_app, real_db, dispatcher_client):
        _seed_search(real_db, "ss-theirs-co", company_id=2, user_id=3)

        resp = dispatcher_client.delete(f"{BASE}/ss-theirs-co")
        assert resp.status_code == 404
        assert _count(real_db, "ss-theirs-co") == 1

    def test_same_company_other_user_404_and_row_kept(self, mobile_app, real_db, dispatcher_client):
        # Same company (1) but owned by a different user (3, manager) — not
        # owned by the dispatcher (user 2) → 404.
        _seed_search(real_db, "ss-other-user", company_id=1, user_id=3)

        resp = dispatcher_client.delete(f"{BASE}/ss-other-user")
        assert resp.status_code == 404
        assert _count(real_db, "ss-other-user") == 1

    def test_missing_search_404(self, mobile_app, real_db, dispatcher_client):
        resp = dispatcher_client.delete(f"{BASE}/ss-does-not-exist")
        assert resp.status_code == 404

"""Freight load negotiation thread tests (Tier-2) — REAL DB.

Covers ``GET/POST /api/v1/freight/loads/{provider_id}/{load_id}/negotiation``:
empty thread, counter chain (parent links + direction), accept/reject terminal,
cross-company isolation, 403 non-dispatcher, 422 (bad action, counter without
amount, negative amount), and the dispatcher happy path.  The thread is a LOCAL
provider-agnostic record — no external TransEu/TIMOCOM call is made.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.mobile.conftest import _override_auth, _role_user

BASE = "/api/v1/freight/loads/trans_eu/LOAD-1/negotiation"


def _seed_record(db, *, id_, company_id, status="offered", amount_eur=None,
                 parent=None, direction="inbound") -> None:
    db.execute(
        "INSERT INTO freight_negotiations (id, company_id, provider_id, provider_load_id, "
        "direction, status, amount_eur, currency, counterparty_name, counterparty_id, "
        "parent_negotiation_id, created_by, created_at, updated_at) "
        "VALUES (?, ?, 'trans_eu', 'LOAD-1', ?, ?, ?, 'EUR', 'Provider Co', 'p-1', ?, 1, "
        "'2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')",
        (id_, company_id, direction, status, amount_eur, parent),
    )
    db.conn.commit()


class TestFreightNegotiation:
    def test_empty_thread_returns_empty_list(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == {"thread": []}

    def test_counter_chain_links_parent_and_direction(self, mobile_app, real_db, mobile_client):
        r1 = mobile_client.post(BASE, json={"action": "counter", "amount_eur": 900})
        assert r1.status_code == 200, r1.text
        n1 = r1.json()["negotiation"]
        assert n1["status"] == "countered"
        assert n1["direction"] == "inbound"  # first record = provider base offer
        assert n1["parent_negotiation_id"] is None
        assert n1["amount_eur"] == 900

        r2 = mobile_client.post(BASE, json={"action": "counter", "amount_eur": 850})
        assert r2.status_code == 200, r2.text
        n2 = r2.json()["negotiation"]
        assert n2["status"] == "countered"
        assert n2["direction"] == "outbound"  # our reply
        assert n2["parent_negotiation_id"] == n1["id"]

        thread = mobile_client.get(BASE).json()["thread"]
        assert len(thread) == 2
        assert thread[0]["id"] == n1["id"]
        assert thread[1]["parent_negotiation_id"] == thread[0]["id"]

    def test_accept_is_terminal(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.post(BASE, json={"action": "accept", "amount_eur": 950})
        assert resp.status_code == 200, resp.text
        n = resp.json()["negotiation"]
        assert n["status"] == "accepted"
        assert n["direction"] == "inbound"
        thread = mobile_client.get(BASE).json()["thread"]
        assert len(thread) == 1 and thread[0]["status"] == "accepted"

    def test_reject_is_terminal(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.post(BASE, json={"action": "reject"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["negotiation"]["status"] == "rejected"

    def test_cross_company_isolation(self, mobile_app, real_db, mobile_client):
        # Company 2 already has a thread for the same provider/load — the
        # company-1 dispatcher must neither see it nor append to it.
        _seed_record(real_db, id_=100, company_id=2, status="countered", amount_eur=700)

        resp = mobile_client.get(BASE)
        assert resp.status_code == 200
        assert resp.json() == {"thread": []}

        post = mobile_client.post(BASE, json={"action": "accept", "amount_eur": 800})
        assert post.status_code == 200, post.text
        assert post.json()["negotiation"]["company_id"] == 1

        cnt = real_db.execute(
            "SELECT COUNT(*) AS cnt FROM freight_negotiations WHERE company_id = 2"
        ).fetchone()
        assert dict(cnt)["cnt"] == 1  # company 2's thread untouched

    def test_non_dispatcher_403(self, mobile_app, real_db, driver_user):
        # get_current_user overridden to the DRIVER, but require_dispatcher is
        # NOT overridden → the real gate rejects the driver with 403.
        _override_auth(mobile_app, driver_user, require_gates=False)
        client = TestClient(mobile_app, raise_server_exceptions=False)
        try:
            resp = client.get(BASE)
            assert resp.status_code == 403
        finally:
            mobile_app.dependency_overrides.clear()

    def test_bad_action_422(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.post(BASE, json={"action": "negotiate"})
        assert resp.status_code == 422  # pydantic Literal validation

    def test_counter_without_amount_422(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.post(BASE, json={"action": "counter"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "amount_required"

    def test_counter_negative_amount_422(self, mobile_app, real_db, mobile_client):
        resp = mobile_client.post(BASE, json={"action": "counter", "amount_eur": -5})
        assert resp.status_code == 422  # pydantic ge=0

    def test_dispatcher_allowed_full_flow(self, mobile_app, real_db, mobile_client):
        assert mobile_client.get(BASE).status_code == 200
        resp = mobile_client.post(BASE, json={"action": "counter", "amount_eur": 920})
        assert resp.status_code == 200, resp.text
        assert resp.json()["negotiation"]["status"] == "countered"

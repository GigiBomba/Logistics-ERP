"""Mobile invoicing endpoint tests (blueprint §6.6) — REAL DB + REAL calculator.

Covers: create (totals via the real calc path, empty-line-items 422, numbering),
list (status / client / search / pagination), detail (client + trip context),
draft-only patch, EVERY legal + illegal state-machine transition, per-action
permission boundaries (dispatcher 403 on mutations, OK on reads/pdf/cmr),
generate_xml → valid XML bytes, pdf endpoint, and the full CMR flow
(cmr_number + signature persisted + signed pdf_url download).
"""
from __future__ import annotations

import base64
import json
import os
import re
import xml.etree.ElementTree as ET

import pytest

from tests.mobile.conftest import _vector_input

BASE = "/api/v1/mobile/invoices"

PNG_1x1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQ"
    "AAAABJRU5ErkJggg=="
)


def _create(client, client_id, line_items=None, **extra):
    payload = {"client_id": client_id}
    if line_items is not None:
        payload["line_items"] = line_items
    payload.update(extra)
    return client.post(BASE, json=payload)


class TestInvoiceCreate:
    def test_create_totals_via_real_calc(self, mobile_app, real_db, finance_seed, manager_client):
        items = [_vector_input(0), _vector_input(1), _vector_input(2)]
        resp = _create(manager_client, finance_seed["client_a"], items)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "draft"
        assert body["subtotal_net"] == 370.35 + 950.0 + 319.69
        assert body["total_vat"] == 70.37 + 180.5 + 0.0
        assert body["total_gross"] == 440.72 + 1130.5 + 319.69
        assert body["total_amount"] == body["total_gross"]
        assert len(body["line_items"]) == 3
        assert body["line_items"][0]["taxable_amount"] == 370.35
        assert body["line_items"][0]["vat_amount"] == 70.37
        # Persisted row is company-scoped with the server-computed totals.
        row = dict(real_db.execute(
            "SELECT company_id, status, subtotal_net, total_vat, total_gross "
            "FROM invoices WHERE id = ?", (body["id"],),
        ).fetchone())
        assert row["company_id"] == 1
        assert row["status"] == "draft"
        assert row["total_gross"] == 440.72 + 1130.5 + 319.69

    def test_create_invoice_numbering_reused(self, mobile_app, real_db, finance_seed, manager_client):
        """The mobile create reuses the desktop sequence (INV-{year}-{seq:04d})."""
        r1 = _create(manager_client, finance_seed["client_a"], [_vector_input(0)])
        r2 = _create(manager_client, finance_seed["client_a"], [_vector_input(0)])
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["invoice_number"] != r2.json()["invoice_number"]
        assert re.match(r"^INV-\d{4}-\d{4}$", r1.json()["invoice_number"])

    def test_create_empty_line_items_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = _create(manager_client, finance_seed["client_a"], [])
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "empty_line_items"

    def test_create_missing_line_items_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = _create(manager_client, finance_seed["client_a"])
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "empty_line_items"

    def test_create_default_dates(self, mobile_app, real_db, finance_seed, manager_client):
        from datetime import date, timedelta

        resp = _create(manager_client, finance_seed["client_a"], [_vector_input(0)])
        assert resp.status_code == 201
        body = resp.json()
        assert body["issue_date"] == date.today().isoformat()
        assert body["due_date"] == (date.today() + timedelta(days=30)).isoformat()

    def test_create_due_before_issue_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = _create(
            manager_client, finance_seed["client_a"], [_vector_input(0)],
            issue_date="2026-05-10", due_date="2026-05-01",
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_dates"

    def test_create_trip_id_persisted(self, mobile_app, real_db, finance_seed, manager_client):
        # A fresh trip (all seeded trips already carry an invoice — trip_id is UNIQUE).
        from datetime import date

        cur = real_db.execute(
            "INSERT INTO trips (company_id, client_id, client_name, driver_id, driver_name, "
            "truck_number, status, start_date, place_of_loading, delivery_country, "
            "distance_km, total_price_eur, net_profit, created_at) "
            "VALUES (1, NULL, 'Fresh Carrier', NULL, NULL, 'FRESH-01', 'Delivered', ?, "
            "'Cluj', 'Vienna', 700, 100, 10, ?)",
            (date.today().isoformat(), date.today().isoformat()),
        )
        real_db.conn.commit()
        trip_id = cur.lastrowid

        resp = _create(manager_client, finance_seed["client_a"], [_vector_input(0)], trip_id=trip_id)
        assert resp.status_code == 201
        assert resp.json()["trip_id"] == trip_id


class TestInvoiceList:
    def test_list_paginated(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(BASE)
        assert resp.status_code == 200
        body = resp.json()
        assert body["page"] == 1 and body["page_size"] == 20
        assert body["total"] >= 7  # 6 seeded + 1 empty
        assert body["total_pages"] >= 1
        assert all("invoice_number" in it and "status" in it for it in body["items"])

    def test_list_status_filter(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(BASE, params={"status": "draft"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] and all(it["status"] == "draft" for it in body["items"])
        # Every seeded draft appears.
        numbers = {it["invoice_number"] for it in body["items"]}
        assert f"INV1-SEED-DRAFT" in numbers

    def test_list_client_filter(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(BASE, params={"client_id": finance_seed["client_a"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] and all(it["client_id"] == finance_seed["client_a"] for it in body["items"])

    def test_list_search_by_number(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(BASE, params={"search": "SEED-FINALIZED"})
        assert resp.status_code == 200
        body = resp.json()
        assert any("SEED-FINALIZED" in it["invoice_number"] for it in body["items"])

    def test_list_search_by_client_name(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(BASE, params={"search": "Globex"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["items"] and all(it["client_name"] == "Globex Ltd" for it in body["items"])

    def test_list_other_company_invisible(self, mobile_app, real_db, records_seed, manager_client):
        # Seed an invoice under company 2 → not visible under company 1.
        from datetime import date

        real_db.execute(
            "INSERT INTO invoices (trip_id, invoice_number, issue_date, due_date, total_amount, "
            "status, company_id, client_id, created_at, updated_at) "
            "VALUES (NULL, 'INV2-OTHER', '2026-01-01', '2026-02-01', 100, 'draft', 2, NULL, "
            "'2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        )
        real_db.conn.commit()
        resp = manager_client.get(BASE, params={"search": "INV2-OTHER"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_list_page_bounds_422(self, mobile_app, real_db, finance_seed, manager_client):
        assert manager_client.get(BASE, params={"page_size": 999}).status_code == 422
        assert manager_client.get(BASE, params={"page": 0}).status_code == 422


class TestInvoiceDetail:
    def test_detail_with_client_and_trip(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_draft"]
        resp = manager_client.get(f"{BASE}/{invoice_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["invoice_number"] == "INV1-SEED-DRAFT"
        assert body["client_name"] == "ACME Corp"
        assert body["client_vat"] == "RO12345"
        assert body["trip_id"] is not None
        assert body["trip_origin"] == "Bucharest"
        assert body["trip_destination"] == "Vienna"
        assert body["truck_number"]
        assert body["driver_name"] == "Ion Popescu"
        assert body["line_items"][0]["taxable_amount"] == 370.35

    def test_detail_404_missing(self, mobile_app, real_db, finance_seed, manager_client):
        assert manager_client.get(f"{BASE}/999999").status_code == 404

    def test_detail_404_other_company(self, mobile_app, real_db, records_seed, manager_client):
        from tests.mobile.conftest import seed_finance, seed_records

        seed_records(real_db, company_id=2)
        other = seed_finance(real_db, company_id=2)
        resp = manager_client.get(f"{BASE}/{other['invoice_draft']}")
        assert resp.status_code == 404


class TestInvoicePatch:
    def test_patch_draft(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_draft"]
        resp = manager_client.patch(f"{BASE}/{invoice_id}", json={"notes": "Updated via mobile"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated via mobile"

    def test_patch_recalculates_totals(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_draft"]
        resp = manager_client.patch(
            f"{BASE}/{invoice_id}",
            json={"line_items": [_vector_input(1)]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_gross"] == 1130.5
        assert body["subtotal_net"] == 950.0

    def test_patch_finalized_422_not_editable(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_finalized"]
        resp = manager_client.patch(f"{BASE}/{invoice_id}", json={"notes": "nope"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "not_editable"

    def test_patch_paid_422_not_editable(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.patch(f"{BASE}/{finance_seed['invoice_paid']}", json={"notes": "nope"})
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "not_editable"


class TestInvoiceTransitions:
    def _transition(self, client, invoice_id, action):
        return client.post(f"{BASE}/{invoice_id}/transition", json={"action": action})

    # ── Legal paths ──
    def test_finalize_draft(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_draft"], "finalize")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "finalized"

    def test_finalize_with_zero_items_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_empty"], "finalize")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "empty_line_items"

    def test_generate_xml_from_finalized(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_finalized"]
        resp = self._transition(manager_client, invoice_id, "generate_xml")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "xml_generated"
        assert body["efactura_xml_path"] and os.path.isfile(body["efactura_xml_path"])
        # Valid XML bytes: parses, root is an Invoice, carries the number.
        with open(body["efactura_xml_path"], "rb") as fh:
            xml_bytes = fh.read()
        assert b"<?xml" in xml_bytes[:64]
        root = ET.fromstring(xml_bytes)
        assert root.tag.endswith("Invoice")
        ns = {"cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"}
        cbc_id = root.find("cbc:ID", ns)
        assert cbc_id is not None and cbc_id.text == "INV1-SEED-FINALIZED"

    def test_submit_after_generate_xml(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_xml"]
        resp = self._transition(manager_client, invoice_id, "submit")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "submitted_externally"
        assert body["efactura_submission_id"] and body["efactura_submission_id"].startswith("EFAC-")

    def test_submit_after_generate_xml_from_finalized(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_finalized"]
        assert self._transition(manager_client, invoice_id, "generate_xml").status_code == 200
        resp = self._transition(manager_client, invoice_id, "submit")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "submitted_externally"

    def test_mark_paid_after_finalize(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_finalized"]
        assert self._transition(manager_client, invoice_id, "mark_paid").status_code == 200
        body = self._transition(manager_client, invoice_id, "mark_paid").json()
        # already paid → terminal; second mark_paid must be rejected by the machine
        assert body is not None

    def test_mark_paid_after_finalize_terminal_422(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_finalized"]
        assert self._transition(manager_client, invoice_id, "mark_paid").status_code == 200
        resp = self._transition(manager_client, invoice_id, "mark_paid")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_mark_paid_after_accepted(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_accepted"], "mark_paid")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "paid"

    def test_cancel_draft(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_draft"], "cancel")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"

    def test_cancel_finalized(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_finalized"], "cancel")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "cancelled"

    # ── Illegal transitions (must 422 with machine-readable error_code) ──
    def test_generate_xml_from_draft_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_draft"], "generate_xml")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_submit_before_generate_xml_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_draft"], "submit")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_mark_paid_before_finalize_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_draft"], "mark_paid")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_cancel_terminal_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_paid"], "cancel")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_cancel_cancelled_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_cancelled"], "cancel")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_finalize_paid_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = self._transition(manager_client, finance_seed["invoice_paid"], "finalize")
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_transition"

    def test_status_unchanged_after_failed_transition(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_draft"]
        resp = self._transition(manager_client, invoice_id, "mark_paid")
        assert resp.status_code == 422
        row = dict(real_db.execute(
            "SELECT status FROM invoices WHERE id = ?", (invoice_id,),
        ).fetchone())
        assert row["status"] == "draft"


class TestInvoicePermissions:
    @pytest.mark.parametrize("action", ["finalize", "generate_xml", "submit", "mark_paid", "cancel"])
    def test_dispatcher_403_on_transitions(self, mobile_app, real_db, finance_seed, dispatcher_client, action):
        resp = dispatcher_client.post(
            f"{BASE}/{finance_seed['invoice_draft']}/transition", json={"action": action},
        )
        assert resp.status_code == 403, f"action={action}"

    @pytest.mark.parametrize("action", ["finalize", "generate_xml", "submit", "mark_paid", "cancel"])
    def test_manager_transitions_allowed(self, mobile_app, real_db, finance_seed, manager_client, action):
        # Each action must at least reach the state machine (200 or 422), never 403.
        resp = manager_client.post(
            f"{BASE}/{finance_seed['invoice_draft']}/transition", json={"action": action},
        )
        assert resp.status_code in (200, 422), f"action={action} -> {resp.status_code}"

    def test_dispatcher_create_403(self, mobile_app, real_db, finance_seed, dispatcher_client):
        resp = _create(dispatcher_client, finance_seed["client_a"], [_vector_input(0)])
        assert resp.status_code == 403

    def test_dispatcher_patch_403(self, mobile_app, real_db, finance_seed, dispatcher_client):
        resp = dispatcher_client.patch(f"{BASE}/{finance_seed['invoice_draft']}", json={"notes": "x"})
        assert resp.status_code == 403

    def test_driver_create_403(self, mobile_app, real_db, finance_seed, driver_client):
        resp = _create(driver_client, finance_seed["client_a"], [_vector_input(0)])
        assert resp.status_code == 403

    def test_dispatcher_reads_ok(self, mobile_app, real_db, finance_seed, dispatcher_client):
        assert dispatcher_client.get(BASE).status_code == 200
        assert dispatcher_client.get(f"{BASE}/{finance_seed['invoice_draft']}").status_code == 200
        assert dispatcher_client.get(f"{BASE}/{finance_seed['invoice_draft']}/pdf").status_code == 200

    def test_dispatcher_cmr_ok(self, mobile_app, real_db, finance_seed, dispatcher_client):
        resp = dispatcher_client.post(
            f"{BASE}/{finance_seed['invoice_draft']}/cmr",
            json={"language": "ro", "copies": 1, "signature_png_base64": PNG_1x1},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["cmr_number"]


class TestInvoicePdf:
    def test_pdf_endpoint_200(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.get(f"{BASE}/{finance_seed['invoice_finalized']}/pdf")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"

    def test_pdf_404_other_company(self, mobile_app, real_db, records_seed, manager_client):
        from tests.mobile.conftest import seed_finance, seed_records

        seed_records(real_db, company_id=2)
        other = seed_finance(real_db, company_id=2)
        assert manager_client.get(f"{BASE}/{other['invoice_draft']}/pdf").status_code == 404


class TestInvoiceCmr:
    def test_cmr_flow(self, mobile_app, real_db, finance_seed, manager_client):
        invoice_id = finance_seed["invoice_draft"]
        trip_id = dict(real_db.execute(
            "SELECT trip_id FROM invoices WHERE id = ?", (invoice_id,),
        ).fetchone())["trip_id"]

        resp = manager_client.post(
            f"{BASE}/{invoice_id}/cmr",
            json={
                "language": "ro",
                "copies": 3,
                "include_stamps": True,
                "sender_name": "Sender Test",
                "sender_address": "Str. Test 1",
                "carrier_name": "Carrier Test",
                "carrier_license": "LIC-CARRIER",
                "remarks": "Handle with care",
                "signature_png_base64": PNG_1x1,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert re.match(r"^CMR-\d{4}-\d{6}$", body["cmr_number"])
        assert body["pdf_url"].startswith("/api/v1/mobile/company/export/download/")

        # Trip cmr fields updated by the CMRGenerator.
        trip = dict(real_db.execute(
            "SELECT cmr_number, cmr_status FROM trips WHERE id = ?", (trip_id,),
        ).fetchone())
        assert trip["cmr_number"] == body["cmr_number"]
        assert trip["cmr_status"] == "generated"

        # Signature PNG persisted to the documents table (entity_type='cmr').
        docs = [dict(r) for r in real_db.execute(
            "SELECT entity_type, entity_id, file_path, mime_type FROM documents "
            "WHERE entity_type = 'cmr' AND entity_id = ?", (trip_id,),
        ).fetchall()]
        sig_rows = [d for d in docs if d["mime_type"] == "image/png"]
        pdf_rows = [d for d in docs if d["mime_type"] == "application/pdf"]
        assert sig_rows, "signature PNG must be persisted"
        assert os.path.isfile(sig_rows[0]["file_path"])
        with open(sig_rows[0]["file_path"], "rb") as fh:
            assert fh.read() == base64.b64decode(PNG_1x1)
        assert pdf_rows, "CMR PDF must be registered as a document"

        # Signed download URL serves the CMR PDF.
        dl = manager_client.get(body["pdf_url"])
        assert dl.status_code == 200
        assert dl.headers["content-type"] == "application/pdf"
        assert dl.content[:4] == b"%PDF"

    def test_cmr_no_trip_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.post(
            f"{BASE}/{finance_seed['invoice_empty']}/cmr", json={"language": "ro"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "no_trip"

    def test_cmr_invalid_signature_422(self, mobile_app, real_db, finance_seed, manager_client):
        resp = manager_client.post(
            f"{BASE}/{finance_seed['invoice_draft']}/cmr",
            json={"language": "ro", "signature_png_base64": "not-base64!!!"},
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["error_code"] == "invalid_signature"

    def test_cmr_404_other_company(self, mobile_app, real_db, records_seed, manager_client):
        from tests.mobile.conftest import seed_finance, seed_records

        seed_records(real_db, company_id=2)
        other = seed_finance(real_db, company_id=2)
        assert manager_client.post(
            f"{BASE}/{other['invoice_draft']}/cmr", json={"language": "ro"},
        ).status_code == 404


class TestInvoiceMachineContract:
    def test_real_transition_table_used(self):
        """The endpoints enforce the REAL desktop machine table."""
        from models.invoice_models import INVOICE_STATUS_TRANSITIONS

        assert INVOICE_STATUS_TRANSITIONS["draft"] == ["finalized", "cancelled"]
        assert INVOICE_STATUS_TRANSITIONS["finalized"] == ["xml_generated", "cancelled", "paid"]
        assert INVOICE_STATUS_TRANSITIONS["xml_generated"] == ["submitted_externally", "draft"]
        assert INVOICE_STATUS_TRANSITIONS["accepted"] == ["paid"]
        assert INVOICE_STATUS_TRANSITIONS["cancelled"] == []
        assert INVOICE_STATUS_TRANSITIONS["paid"] == []

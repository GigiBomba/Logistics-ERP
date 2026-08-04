"""Incremental RBAC gate matrix test (blueprint §13.4) — Phase 1A + 2A endpoints.

Loads ``shared/test_vectors/permission_matrix.json`` (generated in Phase 0 from
the REAL ``PermissionService``) and walks every (role, can_*) pair that maps to
a Phase-1A/2A endpoint.  Each endpoint's PermissionService gate must match the
matrix: denied role → 403, allowed role → non-403.

The auth dependencies are ALL overridden to the role user so a 403 can only
come from the endpoint's own permission gate.
"""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from tests.mobile.conftest import _override_auth, _role_user

MATRIX_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "shared",
    "test_vectors",
    "permission_matrix.json",
)

# permission → list of (method, path, body).  ``{id}`` targets are seeded rows
# (1/2).  Phase 2A adds can_view_analytics (4 endpoints) + can_export_data.
# Phase 3A adds the finance gates: can_create_invoice, can_finalize_invoice
# (4 transition actions), can_cancel_invoice, can_schedule_maintenance
# (schedule-create endpoint) and can_generate_cmr.
ENDPOINTS_BY_PERMISSION = {
    "can_create_vehicle": [("POST", "/api/v1/mobile/fleet", {"plate_number": "RBAC-01", "manufacturer": "Volvo"})],
    "can_update_vehicle": [("PATCH", "/api/v1/mobile/fleet/1", {"status": "Active"})],
    "can_delete_vehicle": [("DELETE", "/api/v1/mobile/fleet/1", None)],
    "can_schedule_maintenance": [
        ("POST", "/api/v1/mobile/fleet/1/maintenance",
         {"date": "2026-01-01", "category": "Repair", "cost": 10.0}),
        ("POST", "/api/v1/mobile/maintenance/schedule",
         {"truck_id": 1, "maintenance_type": "RBAC Service", "interval_months": 3}),
    ],
    "can_create_driver": [("POST", "/api/v1/mobile/drivers", {"name": "RBAC Driver"})],
    "can_update_driver": [("PATCH", "/api/v1/mobile/drivers/1", {"phone": "0700000000"})],
    "can_create_client": [("POST", "/api/v1/mobile/clients", {"name": "RBAC Client"})],
    "can_update_client": [("PATCH", "/api/v1/mobile/clients/1", {"name": "RBAC Updated"})],
    "can_merge_clients": [("POST", "/api/v1/mobile/clients/merge", {"target_id": 1, "source_ids": [2]})],
    # ── Phase 2A: analytics data endpoints (can_view_analytics, dispatcher 403) ──
    "can_view_analytics": [
        ("GET", "/api/v1/mobile/analytics/revenue", None),
        ("GET", "/api/v1/mobile/analytics/fleet-utilization", None),
        ("GET", "/api/v1/mobile/analytics/driver-performance", None),
        ("GET", "/api/v1/mobile/analytics/invoice-aging", None),
    ],
    # ── Phase 2A: history async export (can_export_data, dispatcher allowed) ──
    "can_export_data": [
        ("POST", "/api/v1/mobile/history/trips/export", {"format": "csv"}),
    ],
    # ── Phase 3A: finance gates ──
    "can_create_invoice": [
        ("POST", "/api/v1/mobile/invoices",
         {"client_id": 1, "line_items": [{"description": "RBAC", "quantity": 1, "unit_price": 10.0}]}),
    ],
    "can_finalize_invoice": [
        ("POST", "/api/v1/mobile/invoices/1/transition", {"action": "finalize"}),
        ("POST", "/api/v1/mobile/invoices/1/transition", {"action": "generate_xml"}),
        ("POST", "/api/v1/mobile/invoices/1/transition", {"action": "submit"}),
        ("POST", "/api/v1/mobile/invoices/1/transition", {"action": "mark_paid"}),
    ],
    "can_cancel_invoice": [
        ("POST", "/api/v1/mobile/invoices/1/transition", {"action": "cancel"}),
    ],
    "can_generate_cmr": [
        ("POST", "/api/v1/mobile/invoices/1/cmr",
         {"trip_id": 1, "language": "ro", "copies": 1, "include_stamps": False}),
    ],
    # ── Phase 4A: team management (can_manage_users × 3 endpoints) ──
    "can_manage_users": [
        ("GET", "/api/v1/mobile/team", None),
        ("POST", "/api/v1/mobile/team/invite", {"email": "rbac-invite@test.com", "role": "dispatcher"}),
        ("PATCH", "/api/v1/mobile/team/1", {"role": "manager"}),
    ],
    # ── Phase 4A: company settings (view ×1, manage ×2) ──
    "can_view_company_settings": [
        ("GET", "/api/v1/mobile/settings/company", None),
    ],
    "can_manage_company_settings": [
        ("PATCH", "/api/v1/mobile/settings/company", {}),
        ("POST", "/api/v1/mobile/settings/test-email", {"recipient": "rbac@test.com"}),
    ],
    # ── Phase 4A: tachograph (can_upload_document ×2; dispatcher allowed) ──
    "can_upload_document": [
        # multipart tuple: (method, path, json_body, multipart)
        ("POST", "/api/v1/mobile/tacho/import", None,
         {"data": {"driver_id": "1"},
          "files": {"file": ("rbac.ddd", b"not-a-real-ddd", "application/octet-stream")}}),
        ("GET", "/api/v1/mobile/tacho/import/1/status", None),
    ],
}

ROLE_USERS = {
    "admin": _role_user(1, "admin@test.com", "admin", is_admin=True),
    "dispatcher": _role_user(2, "dispatcher@test.com", "dispatcher", is_admin=False),
    "manager": _role_user(3, "manager@test.com", "manager", is_admin=False),
    "driver": _role_user(4, "driver@test.com", "driver", is_admin=False),
}


def _seed_matrix_rows(real_db) -> None:
    real_db.execute(
        "INSERT INTO trucks (id, plate_number, manufacturer, model, status, year, vin, company_id) "
        "VALUES (1, 'RBAC-TRUCK', 'Volvo', 'FH', 'Active', 2022, 'VIN-RBAC-1', 1)"
    )
    real_db.execute(
        "INSERT INTO drivers (id, name, phone, license_number, is_active, company_id, created_at, updated_at) "
        "VALUES (1, 'RBAC Driver', '0700000000', 'LIC-RBAC-1', 1, 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    for cid, name in ((1, "RBAC Target"), (2, "RBAC Source")):
        real_db.execute(
            "INSERT INTO clients (id, name, contact_person, phone, email, address, vat_number, "
            "currency_preference, notes, is_active, created_at, updated_at, client_type, "
            "payment_terms_days, credit_limit_eur, default_rate_per_km, rating, company_id) "
            "VALUES (?, ?, '', '', '', '', '', 'EUR', '', 1, '2026-01-01T00:00:00Z', "
            "'2026-01-01T00:00:00Z', '', 30, 0, NULL, 4, 1)",
            (cid, name),
        )
    # Phase 3A: trip + draft invoice (with line items) so transition/CMR gates
    # reach the state machine for allowed roles (non-403) without crashing.
    real_db.execute(
        "INSERT INTO trips (id, company_id, client_id, client_name, driver_id, driver_name, "
        "truck_number, status, start_date, place_of_loading, delivery_country, distance_km, "
        "total_price_eur, net_profit, created_at) "
        "VALUES (1, 1, 1, 'RBAC Target', 1, 'RBAC Driver', 'RBAC-TRUCK', 'Delivered', "
        "'2026-01-01', 'Bucharest', 'Vienna', 800, 1000.0, 100.0, '2026-01-01T00:00:00Z')"
    )
    real_db.execute(
        "INSERT INTO invoices (id, trip_id, invoice_number, issue_date, due_date, status, "
        "company_id, client_id, currency, line_items_json, subtotal_net, total_vat, "
        "total_gross, total_amount, created_at, updated_at) "
        "VALUES (1, 1, 'INV-RBAC-1', '2026-01-01', '2026-02-01', 'draft', 1, 1, 'EUR', "
        "'[{\"description\": \"RBAC\", \"quantity\": 1, \"unit_price\": 10.0, "
        "\"vat_rate\": 19.0, \"discount_amount\": 0.0, \"discount_percent\": 0.0}]', "
        "10.0, 1.9, 11.9, 11.9, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    real_db.conn.commit()


class TestMobileRbacMatrix:
    def test_phase1a_endpoint_gates_match_matrix(self, mobile_app, real_db, monkeypatch):
        # Tacho imports would hand fake bytes to the REAL external parser
        # binary — stub the binary probe + execution so the import endpoint
        # stays deterministic and fast (the REAL _process_driver_card still
        # runs, producing zero activity days).
        import json as _json
        import subprocess as _subprocess

        from services.tacho_service import TachoService

        monkeypatch.setattr(
            TachoService, "_resolve_parser_path", lambda self: "/fake/tachograph.exe"
        )
        monkeypatch.setattr(
            TachoService, "_run_parser",
            lambda self, file_bytes: _subprocess.CompletedProcess(
                args=[], returncode=0,
                stdout=_json.dumps(
                    {"type": "CARD", "driverCard": {"activityDailyRecords": []}}
                ).encode(),
            ),
        )

        _seed_matrix_rows(real_db)
        with open(MATRIX_PATH, encoding="utf-8") as fh:
            matrix = json.load(fh)

        checked = 0
        failures: list[str] = []
        for row in matrix:
            role = row["role"]
            permission = row["permission"]
            endpoints = ENDPOINTS_BY_PERMISSION.get(permission)
            if not endpoints:
                continue
            if role not in ROLE_USERS:
                continue

            for entry in endpoints:
                method, path = entry[0], entry[1]
                body = entry[2] if len(entry) > 2 else None
                multipart = entry[3] if len(entry) > 3 else None
                _override_auth(mobile_app, ROLE_USERS[role], require_gates=True)
                client = TestClient(mobile_app, raise_server_exceptions=False)
                if multipart:
                    resp = client.request(
                        method, path,
                        data=multipart.get("data", {}),
                        files=multipart.get("files", {}),
                    )
                else:
                    resp = client.request(method, path, json=body)

                checked += 1
                if not row["expected_allowed"] and resp.status_code != 403:
                    failures.append(
                        f"{role} {permission} {path}: matrix says DENIED, expected 403, got {resp.status_code}"
                    )
                if row["expected_allowed"] and resp.status_code == 403:
                    failures.append(
                        f"{role} {permission} {path}: matrix says ALLOWED, expected non-403, got 403"
                    )
        mobile_app.dependency_overrides.clear()

        # Phase-1 gates (9×4) + analytics (4×4) + export (1×4) = 56
        # Phase 3A: +1×4 create_invoice, +4×4 finalize_invoice transitions,
        # +1×4 cancel_invoice, +1×4 schedule-maintenance endpoint,
        # +1×4 generate_cmr  → 32 more endpoint gates (5 permissions × 4 roles).
        # Phase 4A: can_manage_users ×3, can_view_company_settings ×1,
        # can_manage_company_settings ×2, can_upload_document ×2 → 8×4 = 32 more.
        assert checked >= 120, f"expected to check at least 120 endpoint gates, checked {checked}"
        assert not failures, "\n".join(failures)

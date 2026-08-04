"""Local Download manifest — multi-tenant isolation + signed-URL replay.

Endpoints under test (blueprint §5.3):
  - ``POST /api/v1/mobile/company/export/manifest``
  - ``GET  /api/v1/mobile/company/export/download/{token}``
(``backend/api/v1/mobile.py``).

Rules enforced here (blueprint §5.3 + §1.8, Gate 1 adjudication):
- company A cannot list company B's files — ``company_id`` comes from the
  JWT only, never from the client body;
- every manifest entry carries an HMAC-signed short-lived ``download_url``
  with ``url_expires_at``;
- a signed URL is **still tenant-checked at fetch time**: company Y's URL
  replayed under company X's JWT → 403/404; expired tokens → 403; tampered
  signatures → 403; a company's own URL → 200.

Uses the shared module-scoped fixtures from ``tests/security/conftest.py``
(client, auth_a, auth_b) and seeds two companies' documents directly.
"""
from __future__ import annotations

import inspect
import os
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from conftest import TEST_DB_PATH as _TEST_DB_PATH  # type: ignore[import-not-found]

_MANIFEST_URL = "/api/v1/mobile/company/export/manifest"
_DOWNLOAD_PREFIX = "/api/v1/mobile/company/export/download/"

# Expected exact response/entry shapes — signed-URL manifest contract.
_EXPECTED_ENTRY_KEYS = {
    "record_id", "filename", "size_bytes", "download_url", "url_expires_at",
}


def _seed_documents() -> None:
    """Insert documents for Company A (2) and Company B (1) into the test DB.

    Also writes the actual files to ``data/documents/`` so the download
    endpoint can stream real bytes.
    """
    db_path = os.environ.get("OPERION_DB_PATH", _TEST_DB_PATH)
    conn = sqlite3.connect(db_path, timeout=3)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=500")
    db = type("DbWrapper", (), {"conn": conn})()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"

    def _insert(
        doc_id: int, company_id: int, doc_number: str, title: str, category: str,
        file_name: str, file_size: int, uploaded_at: str,
    ) -> None:
        db.conn.execute(
            """INSERT OR IGNORE INTO documents
               (id, doc_number, title, category, entity_type, entity_id,
                file_path, file_name, file_size, mime_type, tags, description,
                is_archived, uploaded_by, uploaded_at, updated_at, company_id)
               VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, 'application/pdf',
                       '[]', '', 0, 'seed', ?, ?, ?)""",
            (
                doc_id, doc_number, title, category, "",
                f"data/documents/{file_name}", file_name, file_size,
                uploaded_at, uploaded_at, company_id,
            ),
        )
        # Materialize the file so downloads can stream real bytes.
        file_path = os.path.join("data", "documents", file_name)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as fh:
            fh.write(f"seed-content-{doc_id}".encode("utf-8"))

    # Company A — one CMR (general documents), one invoice.
    _insert(1, 1, "DOC-A-0001", "CMR Trip 100", "cmr", "cmr-100.pdf", 12_345,
            f"{now[:-1]}T09:00:00")
    _insert(2, 1, "DOC-A-0002", "Invoice INV-200", "invoice", "invoice-200.pdf",
            98_765, "2026-01-05T10:00:00Z")

    # Company B — one file, must NEVER be visible to Company A
    _insert(3, 2, "DOC-B-0001", "CMR Trip 300", "cmr", "cmr-300.pdf", 55_555,
            f"{now[:-1]}T12:00:00")

    db.conn.commit()
    db.conn.close()


def _token_from_url(url: str) -> str:
    return url.rsplit("/", 1)[-1]


@pytest.fixture(scope="module")
def _documents_seeded(app):
    """Seed documents once per module (after the app/schema is ready)."""
    _seed_documents()


class TestLocalDownloadCompanyIsolation:
    """Company A cannot list company B's files — and vice versa."""

    def test_company_a_cannot_list_company_b_files(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "documents"},
            headers=auth_a,
        )
        assert resp.status_code == 200, f"Manifest failed: {resp.text}"

        entries = resp.json()
        seen_ids = {e["record_id"] for e in entries}
        assert seen_ids == {"1"}, (
            f"Company A 'documents' should see exactly its own doc 1, got {seen_ids}"
        )
        # Company B's document id=3 must never leak.
        assert "3" not in seen_ids

        resp_inv = client.post(
            _MANIFEST_URL,
            json={"category": "invoices"},
            headers=auth_a,
        )
        assert resp_inv.status_code == 200
        inv_ids = {e["record_id"] for e in resp_inv.json()}
        assert inv_ids == {"2"}, (
            f"Company A 'invoices' should see exactly its own doc 2, got {inv_ids}"
        )

        filenames = {e["filename"] for e in entries}
        assert "cmr-100.pdf" in filenames
        assert "cmr-300.pdf" not in filenames

    def test_company_b_cannot_list_company_a_files(
        self, client, auth_b: dict, _documents_seeded,
    ) -> None:
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "documents"},
            headers=auth_b,
        )
        assert resp.status_code == 200, f"Manifest failed: {resp.text}"

        entries = resp.json()
        seen_ids = {e["record_id"] for e in entries}
        assert seen_ids == {"3"}, (
            f"Company B should see exactly its own documents (3), got {seen_ids}"
        )
        assert {e["filename"] for e in entries} == {"cmr-300.pdf"}

    def test_company_id_never_read_from_body(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        """Client-supplied company_id is ignored — scoping is JWT-only."""
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "documents", "company_id": 2},  # body attempts to spoof
            headers=auth_a,
        )
        assert resp.status_code == 200
        seen_ids = {e["record_id"] for e in resp.json()}
        # Company A's JWT still scopes the query to company 1.
        assert "3" not in seen_ids
        assert seen_ids == {"1"}

    def test_unauthorized_requests_rejected(self, client) -> None:
        resp = client.post(_MANIFEST_URL, json={"category": "documents"})
        assert resp.status_code == 401

    def test_trip_history_manifest_is_company_scoped(
        self, client, auth_a: dict, auth_b: dict,
    ) -> None:
        """``trip_history`` category maps to the trips table, company-scoped."""
        resp_a = client.post(
            _MANIFEST_URL,
            json={"category": "trip_history"},
            headers=auth_a,
        )
        assert resp_a.status_code == 200
        ids_a = {e["record_id"] for e in resp_a.json()}
        # conftest seeds trips 1, 2 for Company A and 3, 4 for Company B.
        assert ids_a == {"1", "2"}, f"Company A trip_history IDs: {ids_a}"

        resp_b = client.post(
            _MANIFEST_URL,
            json={"category": "trip_history"},
            headers=auth_b,
        )
        assert resp_b.status_code == 200
        ids_b = {e["record_id"] for e in resp_b.json()}
        assert ids_b == {"3", "4"}, f"Company B trip_history IDs: {ids_b}"


class TestManifestFilters:
    """Category + date-range filters."""

    def test_category_filter(self, client, auth_a: dict, _documents_seeded) -> None:
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "invoices"},
            headers=auth_a,
        )
        assert resp.status_code == 200
        entries = resp.json()
        assert [e["filename"] for e in entries] == ["invoice-200.pdf"]

    def test_ocr_results_category_matches_ocr_processed_documents(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        """``ocr_results`` returns documents that have actually been OCR'd."""
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "ocr_results"},
            headers=auth_a,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_date_range_filter(self, client, auth_a: dict, _documents_seeded) -> None:
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "invoices", "date_from": "2026-01-01", "date_to": "2026-01-31"},
            headers=auth_a,
        )
        assert resp.status_code == 200
        filenames = {e["filename"] for e in resp.json()}
        # Only the 2026-01-05 invoice falls inside the window.
        assert filenames == {"invoice-200.pdf"}

    def test_invalid_to_date_rejected(self, client, auth_a: dict) -> None:
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "documents", "date_to": "not-a-date"},
            headers=auth_a,
        )
        assert resp.status_code == 400
        assert "to_date" in resp.json().get("detail", "")

    def test_invalid_from_date_rejected(self, client, auth_a: dict) -> None:
        """``date_from`` is validated symmetrically with ``date_to`` (Gate-2
        readability fix: it used to reach SQL unvalidated)."""
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "documents", "date_from": "not-a-date"},
            headers=auth_a,
        )
        assert resp.status_code == 400
        assert "from_date" in resp.json().get("detail", "")

    def test_both_directions_rejected_for_trip_history(
        self, client, auth_a: dict,
    ) -> None:
        """The trip_history branch validates ``date_from`` and ``date_to``."""
        resp_from = client.post(
            _MANIFEST_URL,
            json={"category": "trip_history", "date_from": "nope"},
            headers=auth_a,
        )
        assert resp_from.status_code == 400
        assert "from_date" in resp_from.json().get("detail", "")

        resp_to = client.post(
            _MANIFEST_URL,
            json={"category": "trip_history", "date_to": "nope"},
            headers=auth_a,
        )
        assert resp_to.status_code == 400
        assert "to_date" in resp_to.json().get("detail", "")

    def test_valid_date_from_accepted(self, client, auth_a: dict, _documents_seeded) -> None:
        """A well-formed ISO date_from is accepted (not over-rejected)."""
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "invoices", "date_from": "2026-01-01"},
            headers=auth_a,
        )
        assert resp.status_code == 200
        assert [e["filename"] for e in resp.json()] == ["invoice-200.pdf"]

    def test_entry_shape_matches_signed_url_contract(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        """Every entry has exactly the manifest fields — record_id, filename,
        size_bytes, download_url, url_expires_at. No id/category/modified_at."""
        resp = client.post(
            _MANIFEST_URL,
            json={"category": "documents"},
            headers=auth_a,
        )
        assert resp.status_code == 200
        for entry in resp.json():
            assert set(entry.keys()) == _EXPECTED_ENTRY_KEYS
            assert isinstance(entry["record_id"], str)
            assert isinstance(entry["size_bytes"], int)
            assert entry["download_url"].startswith(_DOWNLOAD_PREFIX)
            # ISO-8601 parseable expiry in the future.
            expires = datetime.fromisoformat(entry["url_expires_at"].replace("Z", "+00:00"))
            assert expires > datetime.now(timezone.utc) - timedelta(minutes=1)


class TestSignedUrlReplay:
    """A signed URL must be tenant-checked at fetch time, not just at
    manifest-generation time (blueprint §5.3)."""

    def _fetch_manifest_url(self, client, headers, category: str = "documents") -> str:
        resp = client.post(
            _MANIFEST_URL,
            json={"category": category},
            headers=headers,
        )
        assert resp.status_code == 200, f"Manifest failed: {resp.text}"
        entries = resp.json()
        assert entries, "Expected at least one manifest entry"
        return entries[0]["download_url"]

    def test_company_own_signed_url_streams_200(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        url = self._fetch_manifest_url(client, auth_a)
        resp = client.get(url, headers=auth_a)
        assert resp.status_code == 200, f"Own URL should stream: {resp.text}"
        assert resp.content == b"seed-content-1"
        assert resp.headers.get("content-type", "").startswith("application/pdf")

    def test_company_y_url_replayed_under_company_x_jwt_rejected(
        self, client, auth_a: dict, auth_b: dict, _documents_seeded,
    ) -> None:
        """Company Y's signed URL fetched under Company X's JWT → 403/404."""
        url_b = self._fetch_manifest_url(client, auth_b)
        resp = client.get(url_b, headers=auth_a)
        assert resp.status_code in (403, 404), (
            f"Replayed cross-company URL should be rejected, got {resp.status_code}"
        )

    def test_company_x_url_rejected_under_company_y_jwt(
        self, client, auth_a: dict, auth_b: dict, _documents_seeded,
    ) -> None:
        url_a = self._fetch_manifest_url(client, auth_a)
        resp = client.get(url_a, headers=auth_b)
        assert resp.status_code in (403, 404), (
            f"Replayed cross-company URL should be rejected, got {resp.status_code}"
        )

    def test_expired_token_rejected(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        from backend.services.local_download_service import (
            KIND_DOCUMENT,
            create_download_token,
        )

        token = create_download_token(
            record_id="1",
            company_id=1,
            kind=KIND_DOCUMENT,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        resp = client.get(f"{_DOWNLOAD_PREFIX}{token}", headers=auth_a)
        assert resp.status_code == 403, (
            f"Expired token should be rejected with 403, got {resp.status_code}"
        )

    def test_tampered_signature_rejected(
        self, client, auth_a: dict, _documents_seeded,
    ) -> None:
        url = self._fetch_manifest_url(client, auth_a)
        token = _token_from_url(url)
        # Flip the final signature character.
        flipped = token[:-1] + ("0" if token[-1] != "0" else "1")
        resp = client.get(f"{_DOWNLOAD_PREFIX}{flipped}", headers=auth_a)
        assert resp.status_code == 403, (
            f"Tampered signature should be rejected with 403, got {resp.status_code}"
        )

    def test_trip_history_download_streams_json(
        self, client, auth_a: dict,
    ) -> None:
        url = self._fetch_manifest_url(client, auth_a, category="trip_history")
        resp = client.get(url, headers=auth_a)
        assert resp.status_code == 200, f"Trip history download failed: {resp.text}"
        assert resp.headers.get("content-type", "").startswith("application/json")
        assert resp.json()["record_id"] in ("1", "2")

    def test_cross_company_trip_history_url_rejected(
        self, client, auth_a: dict, auth_b: dict,
    ) -> None:
        url_b = self._fetch_manifest_url(client, auth_b, category="trip_history")
        resp = client.get(url_b, headers=auth_a)
        assert resp.status_code in (403, 404)


class TestPullOnDemandShape:
    """Static assertion: the manifest endpoint carries no background-sync
    machinery.

    Local download is pull-on-demand only (blueprint §6.5) — there is no
    Timer/WorkManager/scheduler/celery wiring on the backend side of the
    manifest.  This is asserted statically against the endpoint source so a
    future contributor cannot silently add a background sync path.
    """

    def test_manifest_endpoint_has_no_background_sync_machinery(self) -> None:
        from backend.api.v1 import mobile

        fn = mobile.company_export_manifest
        source = inspect.getsource(fn)
        forbidden_tokens = (
            "BackgroundTasks",
            "Timer(",
            "WorkManager",
            "celery",
            "aioschedule",
            "schedule(",
        )
        for token in forbidden_tokens:
            assert token not in source, (
                f"Manifest endpoint must stay pull-on-demand — found '{token}' "
                "in its source"
            )

    def test_manifest_response_is_a_flat_entry_list(
        self, client, auth_a, _documents_seeded,
    ) -> None:
        resp = client.post(_MANIFEST_URL, json={"category": "documents"}, headers=auth_a)
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        # Exactly the five signed-URL contract fields on every entry.
        for entry in body:
            assert set(entry.keys()) == _EXPECTED_ENTRY_KEYS

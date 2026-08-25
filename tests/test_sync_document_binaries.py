"""Tests for Phase C — document binary sync.

Covers:
- sha256 hash computed on document registration (desktop UploadService).
- Server binary upload stores sha256; same-hash re-upload dedups.
- OCR-once: binary upload with skip_ocr=true doesn't trigger OCR.
- Binary push: SyncEngine uploads local files via ApiClient (multipart, doc id).
- Binary pull: server files downloaded when missing, skipped when present.
- Resiliency: a missing local file doesn't abort the cycle.
- R1/R2 (security): download containment + category traversal on write.
- R3 (data loss): binary pull file_path UPDATE is echo-suppressed.
- R4 (corruption): multipart retry re-sends full bytes, not an exhausted handle.
- R5 (data loss): pulled docs start with empty file_path; hash-mismatched
  local files are never silently uploaded over the server binary.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from unittest.mock import MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.dependencies import get_db, get_document_service
from backend.dependencies_security import get_current_user
from backend.main import create_app
from database.db_manager import DatabaseManager
from repositories.document_repository import DocumentRepository
from services.document.upload_service import UploadService
from services.sync_engine import SyncEngine
from services.sync_outbox_service import SyncOutboxService
from services.sync_pull_service import SyncPullService


# ── Shared fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def db_path():
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    try:
        os.unlink(tmp.name)
    except OSError:
        pass


@pytest.fixture
def db(db_path):
    _db = DatabaseManager(db_path)
    for cid in range(0, 101):
        _db.conn.execute(
            "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
            "VALUES (?, ?, 'starter')",
            (cid, f"Company-{cid}"),
        )
    _db.conn.commit()
    yield _db
    try:
        _db.close()
    except Exception:
        pass


def _make_client(db, doc_service=None):
    app = create_app()

    async def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    if doc_service is not None:
        async def _override_doc_service():
            return doc_service

        app.dependency_overrides[get_document_service] = _override_doc_service

    async def _mock_user():
        return {
            "id": 1, "email": "sync@test.com", "role": "admin",
            "is_admin": True, "company_id": 1,
        }

    app.dependency_overrides[get_current_user] = _mock_user
    return TestClient(app)


def _seed_server_document(db, doc_number="DOC-1", company_id=1):
    cur = db.conn.execute(
        "INSERT INTO documents (doc_number, title, category, file_path, "
        "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
        "company_id) "
        "VALUES (?, 'Test', 'other', '', 'test.pdf', 0, 'application/pdf', "
        "'', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', ?)",
        (doc_number, company_id),
    )
    db.conn.commit()
    return cur.lastrowid


def _make_engine(db, fake, device_id="device-A"):
    outbox = SyncOutboxService(db)
    pull = SyncPullService(db, fake)
    return SyncEngine(db, fake, outbox, pull, device_id=device_id)


class _BinaryFakeApiClient:
    """ApiClient stub that records document binary uploads/downloads."""

    def __init__(self, push_handler=None, pull_responses=None, download_content=b""):
        self.online = True
        self.push_handler = push_handler
        self.pull_responses = pull_responses or {}
        self.download_content = download_content
        self.push_calls = []
        self.pull_calls = []
        self.upload_calls = []      # (doc_id, file_path, skip_ocr)
        self.download_calls = []    # (doc_id, dest_path)

    def is_online(self):
        return self.online

    def post(self, path, json=None):
        self.push_calls.append((path, json))
        if self.push_handler is not None:
            return self.push_handler((json or {}).get("items") or [])
        return {"results": []}

    def get(self, path, params=None):
        self.pull_calls.append((path, params))
        entity = (params or {}).get("entity")
        return {
            "records": self.pull_responses.get(entity, []),
            "next_after_id": 0,
            "has_more": False,
        }

    def upload_document_file(self, doc_id, file_path, skip_ocr=False):
        self.upload_calls.append((doc_id, file_path, skip_ocr))
        return {"status": "ok", "id": doc_id, "file_hash": "x"}

    def download_document_file(self, doc_id, dest_path):
        self.download_calls.append((doc_id, dest_path))
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(self.download_content)
        return dest_path


# ── Hash on desktop registration ──────────────────────────────────────────


class TestHashComputed:
    def test_register_existing_computes_sha256(self, db, tmp_path):
        src = tmp_path / "doc.pdf"
        src.write_bytes(b"%PDF-1.4 fake pdf payload")
        svc = UploadService(db, DocumentRepository(db))
        doc_id = svc.register_existing(file_path=str(src), title="Hashed",
                                       category="other")
        assert doc_id is not None
        row = db.conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        expected = hashlib.sha256(src.read_bytes()).hexdigest()
        assert row["file_hash"] == expected


# ── Server binary upload: sha256 + dedup + OCR-once ───────────────────────


class TestServerBinaryUpload:
    def test_upload_stores_sha256_and_same_hash_dedups(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        client = _make_client(db)
        doc_id = _seed_server_document(db)
        content = b"%PDF-1.4 binary content here"

        resp = client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("doc.pdf", content, "application/pdf")},
            data={"skip_ocr": "true"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deduped"] is False
        expected = hashlib.sha256(content).hexdigest()
        assert body["file_hash"] == expected
        row = db.conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
        assert row["file_hash"] == expected
        assert row["file_path"]  # stored to a server path

        # Same-hash re-upload → deduped, no re-store, no error.
        resp2 = client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("doc.pdf", content, "application/pdf")},
            data={"skip_ocr": "true"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["deduped"] is True

    def test_upload_with_skip_ocr_does_not_trigger_ocr(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        doc_id = _seed_server_document(db)

        class _FakeDocService:
            def __init__(self):
                self.ocr = MagicMock()

            def get_by_id(self, doc_id_, company_id=0):
                row = db.conn.execute(
                    "SELECT * FROM documents WHERE id = ? AND company_id = ?",
                    (doc_id_, company_id),
                ).fetchone()
                return dict(row) if row else None

        fake_svc = _FakeDocService()
        client = _make_client(db, doc_service=fake_svc)
        resp = client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("doc.pdf", b"%PDF-1.4 skip me", "application/pdf")},
            data={"skip_ocr": "true"},
        )
        assert resp.status_code == 200
        fake_svc.ocr.enqueue_ocr.assert_not_called()

    def test_upload_without_skip_ocr_triggers_ocr(self, db, monkeypatch, tmp_path):
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        doc_id = _seed_server_document(db)

        class _FakeDocService:
            def __init__(self):
                self.ocr = MagicMock()

            def get_by_id(self, doc_id_, company_id=0):
                row = db.conn.execute(
                    "SELECT * FROM documents WHERE id = ? AND company_id = ?",
                    (doc_id_, company_id),
                ).fetchone()
                return dict(row) if row else None

        fake_svc = _FakeDocService()
        client = _make_client(db, doc_service=fake_svc)
        resp = client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("doc.pdf", b"%PDF-1.4 run ocr", "application/pdf")},
            data={"skip_ocr": "false"},
        )
        assert resp.status_code == 200
        fake_svc.ocr.enqueue_ocr.assert_called_once()
        args = fake_svc.ocr.enqueue_ocr.call_args[0]
        assert args[0] == doc_id
        assert args[2] == "application/pdf"

    def test_download_endpoint_serves_the_file(self, db, monkeypatch, tmp_path):
        """GET /documents/{id}/file serves the stored binary (company-scoped)."""
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        client = _make_client(db)
        doc_id = _seed_server_document(db)
        content = b"%PDF-1.4 download me"
        client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("doc.pdf", content, "application/pdf")},
            data={"skip_ocr": "true"},
        )

        resp = client.get(f"/api/v1/documents/{doc_id}/file")
        assert resp.status_code == 200
        assert resp.content == content
        assert resp.headers.get("content-type", "").startswith("application/pdf")

        # Unknown doc → 404; other company's doc → 404.
        assert client.get("/api/v1/documents/999999/file").status_code == 404


# ── Binary push from SyncEngine ───────────────────────────────────────────


class TestBinaryPush:
    def test_local_file_uploaded_with_document_id(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        local_file = tmp_path / "doc.pdf"
        local_file.write_bytes(b"%PDF-1.4 to push")
        file_hash = hashlib.sha256(local_file.read_bytes()).hexdigest()

        # Local document row with a server mapping (server_id 500).
        local_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('D1', 'Doc', 'other', ?, 'doc.pdf', 0, 'application/pdf', "
            "?, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
            (str(local_file), file_hash),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('document', ?, 500, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()
        # Clear the outbox row created by the INSERT (already pushed).
        outbox = SyncOutboxService(db)
        for r in outbox.pending():
            outbox.mark_synced(r["id"])

        fake = _BinaryFakeApiClient()
        engine = _make_engine(db, fake)
        engine.sync_once()

        assert fake.upload_calls == [(500, str(local_file), True)]
        # Tracking recorded so the next cycle does NOT re-upload.
        assert outbox.get_meta("doc_binary_uploaded:500") == file_hash

        # Second cycle: unchanged → no re-upload.
        engine.sync_once()
        assert len(fake.upload_calls) == 1

    def test_missing_local_file_does_not_abort_cycle(self, db, tmp_path, monkeypatch):
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        # Document row whose file_path points at a file that does NOT exist.
        local_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('D2', 'Ghost', 'other', ?, 'ghost.pdf', 0, 'application/pdf', "
            "'abc', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
            (str(tmp_path / "does_not_exist.pdf"),),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('document', ?, 501, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()
        outbox = SyncOutboxService(db)
        for r in outbox.pending():
            outbox.mark_synced(r["id"])

        fake = _BinaryFakeApiClient()
        engine = _make_engine(db, fake)
        # Must not raise; the missing file is logged + skipped.
        engine.sync_once()
        assert fake.upload_calls == []
        # The cycle still completed (status emitted).
        summaries = []
        engine.sync_finished.connect(summaries.append)
        engine.sync_once()
        assert summaries and summaries[-1]["status"] == "idle"


# ── Binary pull from SyncEngine ───────────────────────────────────────────


class TestBinaryPull:
    def test_server_file_downloaded_when_missing_locally(self, db, tmp_path, monkeypatch):
        docs_root = tmp_path / "docs"
        monkeypatch.setattr(
            "services.document.upload_service.DOCUMENTS_ROOT", str(docs_root)
        )
        content = b"%PDF-1.4 pulled from server"
        file_hash = hashlib.sha256(content).hexdigest()

        local_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('P1', 'Pulled', 'other', '', 'pulled.pdf', 0, 'application/pdf', "
            "?, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
            (file_hash,),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('document', ?, 600, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()
        outbox = SyncOutboxService(db)
        for r in outbox.pending():
            outbox.mark_synced(r["id"])

        fake = _BinaryFakeApiClient(download_content=content)
        engine = _make_engine(db, fake)
        engine.sync_once()

        dest = str(docs_root / "other" / "pulled.pdf")
        assert fake.download_calls == [(600, dest)]
        assert os.path.isfile(dest)
        with open(dest, "rb") as f:
            assert f.read() == content
        # The local row now points at the downloaded file.
        row = db.conn.execute("SELECT file_path FROM documents WHERE id = ?", (local_id,)).fetchone()
        assert row["file_path"] == dest

        # Second cycle: file present + hash matches → no re-download.
        fake.download_calls.clear()
        engine.sync_once()
        assert fake.download_calls == []

    def test_pull_keeps_local_file_path_on_row_update(self, db, tmp_path, monkeypatch):
        """A pulled document row must NOT overwrite the local file_path."""
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        local_file = tmp_path / "local.pdf"
        local_file.write_bytes(b"%PDF-1.4 local")
        file_hash = hashlib.sha256(local_file.read_bytes()).hexdigest()

        local_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('K1', 'Keep', 'other', ?, 'local.pdf', 0, 'application/pdf', "
            "?, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
            (str(local_file), file_hash),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('document', ?, 700, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()

        fake = _BinaryFakeApiClient(pull_responses={
            "document": [
                {"id": 700, "doc_number": "K1", "title": "Keep",
                 "category": "other", "file_path": "/server/elsewhere.pdf",
                 "file_name": "server.pdf", "file_hash": file_hash,
                 "mime_type": "application/pdf",
                 "uploaded_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        }, download_content=b"%PDF-1.4 local")
        engine = _make_engine(db, fake)
        engine.sync_once()

        # The local file_path is preserved (not clobbered by the server path).
        row = db.conn.execute("SELECT file_path FROM documents WHERE id = ?", (local_id,)).fetchone()
        assert row["file_path"] == str(local_file)


# ── R1/R2 (security) ──────────────────────────────────────────────────────


class TestSecurityContainment:
    def test_download_rejects_file_path_outside_documents_root(
        self, db, monkeypatch, tmp_path,
    ):
        """R1: GET /documents/{id}/file must not serve a path outside
        DOCUMENTS_ROOT (attacker-influenced via the sync payload)."""
        docs_root = tmp_path / "docs_root"
        docs_root.mkdir()
        monkeypatch.setattr(
            "services.document.upload_service.DOCUMENTS_ROOT", str(docs_root)
        )
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret")
        doc_id = _seed_server_document(db)
        db.conn.execute(
            "UPDATE documents SET file_path = ?, file_name = 'secret.txt', "
            "mime_type = 'text/plain' WHERE id = ?",
            (str(secret), doc_id),
        )
        db.conn.commit()

        client = _make_client(db)
        # 404 (not 403) — the check must not leak that the path exists.
        resp = client.get(f"/api/v1/documents/{doc_id}/file")
        assert resp.status_code == 404

        # Empty file_path also 404s.
        db.conn.execute(
            "UPDATE documents SET file_path = '' WHERE id = ?", (doc_id,)
        )
        db.conn.commit()
        assert client.get(f"/api/v1/documents/{doc_id}/file").status_code == 404

    def test_upload_category_traversal_stays_under_documents_root(
        self, db, monkeypatch, tmp_path,
    ):
        """R2: a category of '../../..' must never write outside DOCUMENTS_ROOT."""
        docs_root = tmp_path / "docs_root"
        monkeypatch.setattr(
            "services.document.upload_service.DOCUMENTS_ROOT", str(docs_root)
        )
        doc_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('TR1', 'Trav', '../../..', '', 'trav.pdf', 0, 'application/pdf', "
            "'', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
        ).lastrowid
        db.conn.commit()

        client = _make_client(db)
        resp = client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("trav.pdf", b"%PDF-1.4 traversal", "application/pdf")},
            data={"skip_ocr": "true"},
        )
        assert resp.status_code == 200, resp.text
        row = db.conn.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,)).fetchone()
        real = os.path.realpath(row["file_path"])
        root_real = os.path.realpath(str(docs_root))
        # Written inside the root (sanitized category), never escaped it.
        assert real.startswith(root_real + os.sep)
        assert os.path.isfile(real)

    def test_post_file_cross_company_404(self, db, monkeypatch, tmp_path):
        """A document in another company must be unreachable via POST /{id}/file."""
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        doc_id = _seed_server_document(db, company_id=2)
        client = _make_client(db)  # mocked user is company_id 1
        resp = client.post(
            f"/api/v1/documents/{doc_id}/file",
            files={"file": ("doc.pdf", b"%PDF-1.4 other company", "application/pdf")},
            data={"skip_ocr": "true"},
        )
        assert resp.status_code == 404


# ── R3 (echo suppression) ─────────────────────────────────────────────────


class TestBinaryPullEchoSuppression:
    def test_pull_file_path_update_does_not_create_outbox_row(
        self, db, tmp_path, monkeypatch,
    ):
        """R3: the binary pull's file_path UPDATE must NOT be captured by the
        outbox trigger (otherwise the desktop path gets echoed to the server
        and 404s every other device)."""
        docs_root = tmp_path / "docs"
        monkeypatch.setattr(
            "services.document.upload_service.DOCUMENTS_ROOT", str(docs_root)
        )
        content = b"%PDF-1.4 echo suppressed"
        file_hash = hashlib.sha256(content).hexdigest()

        local_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('E1', 'Echo', 'other', '', 'echo.pdf', 0, 'application/pdf', "
            "?, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
            (file_hash,),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('document', ?, 800, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()
        outbox = SyncOutboxService(db)
        for r in outbox.pending():
            outbox.mark_synced(r["id"])

        fake = _BinaryFakeApiClient(download_content=content)
        engine = _make_engine(db, fake)
        engine.sync_once()

        # The binary pull downloaded + updated file_path; no pending outbox
        # row may exist for it (echo-suppressed via set_sync_in_progress).
        pending_docs = [
            r for r in outbox.pending() if r["entity_type"] == "document"
        ]
        assert pending_docs == []
        row = db.conn.execute("SELECT file_path FROM documents WHERE id = ?", (local_id,)).fetchone()
        assert row["file_path"]  # file was downloaded and the row updated


# ── R4 (retry-safe multipart) ─────────────────────────────────────────────


class TestRetrySafeUpload:
    def test_upload_document_file_retry_resends_full_bytes(self, tmp_path):
        """R4: the retry path re-sends the FULL bytes (not an exhausted
        file handle) — otherwise the server stores an empty file."""
        from client.api_client import ApiClient

        src = tmp_path / "retry.pdf"
        content = b"%PDF-1.4 retry-safe content " * 500
        src.write_bytes(content)

        sizes = []
        attempts = [0]

        def handler(request):
            sizes.append(len(request.content))
            attempts[0] += 1
            if attempts[0] == 1:
                return httpx.Response(503, json={"detail": "upstream retry"})
            return httpx.Response(200, json={"status": "ok", "id": 1})

        api = ApiClient("http://server.test")
        api._client = httpx.Client(transport=httpx.MockTransport(handler))
        result = api.upload_document_file(1, str(src), skip_ocr=True)
        assert result == {"status": "ok", "id": 1}
        assert len(sizes) == 2, f"expected a retry, got {len(sizes)} attempts"
        # Both attempts carried the full multipart body (≥ the raw file size).
        assert sizes[0] == sizes[1]
        assert sizes[0] >= len(content)


# ── R5 (silent binary replacement) ────────────────────────────────────────


class TestBinaryPushHashGuard:
    def test_pull_insert_uses_empty_file_path(self, db, tmp_path, monkeypatch):
        """R5: a brand-new pulled document row must NOT keep the server's
        file_path — it could shadow a same-named local file with wrong content.
        (Empty file_hash keeps the binary pull from downloading and setting
        the path, so this asserts the INSERT itself used the placeholder.)"""
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        # No local row yet; the pull creates it from the server payload.
        fake = _BinaryFakeApiClient(pull_responses={
            "document": [
                {"id": 900, "doc_number": "NP1", "title": "New Pull",
                 "category": "other", "file_path": "/server/elsewhere.pdf",
                 "file_name": "shadow.pdf", "file_hash": "",
                 "mime_type": "application/pdf",
                 "uploaded_at": "2026-08-01T00:00:00Z",
                 "updated_at": "2026-08-01T00:00:00Z"},
            ],
        })
        engine = _make_engine(db, fake)
        engine.sync_once()

        row = db.conn.execute(
            "SELECT file_path FROM documents WHERE doc_number = 'NP1'"
        ).fetchone()
        assert row is not None
        assert row["file_path"] == ""

    def test_push_skips_upload_when_local_hash_disagrees(
        self, db, tmp_path, monkeypatch,
    ):
        """R5: a local file whose sha256 disagrees with the row's file_hash
        (external edit / wrong-file shadow) must NOT be silently uploaded."""
        monkeypatch.setattr("services.document.upload_service.DOCUMENTS_ROOT", str(tmp_path))
        local_file = tmp_path / "wrong.pdf"
        local_file.write_bytes(b"%PDF-1.4 wrong content")
        # Row claims a DIFFERENT hash than the actual file.
        row_hash = hashlib.sha256(b"something else entirely").hexdigest()
        local_id = db.conn.execute(
            "INSERT INTO documents (doc_number, title, category, file_path, "
            "file_name, file_size, mime_type, file_hash, uploaded_at, updated_at, "
            "company_id) "
            "VALUES ('M1', 'Mismatch', 'other', ?, 'wrong.pdf', 0, 'application/pdf', "
            "?, '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', 1)",
            (str(local_file), row_hash),
        ).lastrowid
        db.conn.commit()
        db.conn.execute(
            "INSERT INTO sync_id_map (entity_type, local_id, server_id, created_at) "
            "VALUES ('document', ?, 950, '2026-08-01T00:00:00Z')",
            (local_id,),
        )
        db.conn.commit()
        outbox = SyncOutboxService(db)
        for r in outbox.pending():
            outbox.mark_synced(r["id"])

        fake = _BinaryFakeApiClient()
        engine = _make_engine(db, fake)
        engine.sync_once()

        assert fake.upload_calls == []
        # The wrong file must not be tracked as uploaded either.
        assert outbox.get_meta("doc_binary_uploaded:950") is None
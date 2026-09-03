"""Unit tests for the batched UPDATE performance fixes.

DB1 — ``ClientRepository.reassign_contacts``: the per-contact UPDATE loop was
      replaced by a single ``UPDATE ... WHERE id IN (?,...)`` per chunk.
DB2 — ``DocumentRepository.delete_batch``: the per-document UPDATE loop was
      replaced by a single ``UPDATE ... WHERE id IN (?,...)`` per chunk.

These tests prove the batched path issues ONE UPDATE statement (not N) for
inputs within one chunk and preserves the affected-row counts and commit
flow of the previous implementation.
"""

from __future__ import annotations

from repositories.client_repository import ClientRepository
from repositories.document_repository import DocumentRepository
from tests.test_helpers import InMemoryDB


# ── helpers ──────────────────────────────────────────────────────────


def _client(db: InMemoryDB, client_id: int, name: str) -> None:
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, created_at) VALUES (?, ?, '2026-01-01')",
        (client_id, name),
    )
    db.conn.commit()


def _contact(db: InMemoryDB, client_id: int, full_name: str) -> None:
    db.conn.execute(
        "INSERT INTO client_contacts (client_id, full_name, created_at) "
        "VALUES (?, ?, '2026-01-01')",
        (client_id, full_name),
    )


def _doc(db: InMemoryDB, **kw) -> int:
    d = dict(
        doc_number="DOC-2026-0001",
        title="Test Document",
        category="invoice",
        entity_type="trip",
        entity_id=1,
        file_path="/tmp/test.pdf",
        file_name="test.pdf",
        file_size=1024,
        mime_type="application/pdf",
        file_hash="abc123",
        tags="[]",
        description="",
        is_archived=0,
        uploaded_by="tester",
        uploaded_at="2026-06-01T12:00:00Z",
        updated_at="2026-06-01T12:00:00Z",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO documents ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _spy_updates(repo, monkeypatch):
    """Wrap the repo's ``_execute_with_count`` and record UPDATE queries."""
    calls: list[str] = []
    original = repo._execute_with_count

    def spy(query, params=(), commit=False):
        calls.append(query)
        return original(query, params, commit)

    monkeypatch.setattr(repo, "_execute_with_count", spy)
    return calls


# ── DB1: ClientRepository.reassign_contacts ──────────────────────────


class TestReassignContactsBatch:
    def test_single_batched_update_moves_all_contacts(self, monkeypatch):
        db = InMemoryDB()
        _client(db, 1, "Source")
        _client(db, 2, "Target")
        for i in range(3):
            _contact(db, client_id=1, full_name=f"Contact {i}")
        db.conn.commit()

        repo = ClientRepository(db)
        calls = _spy_updates(repo, monkeypatch)

        affected = repo.reassign_contacts(1, 2)

        assert affected == 3, "affected count must match the previous semantics"
        updates = [q for q in calls if q.startswith("UPDATE")]
        assert len(updates) == 1, (
            f"expected ONE batched UPDATE, got {len(updates)}: {updates}"
        )
        assert "IN (?, ?, ?)" in updates[0]
        assert "SET client_id = ?" in updates[0]

        rows = db.conn.execute("SELECT client_id FROM client_contacts").fetchall()
        assert all(r["client_id"] == 2 for r in rows)

    def test_zero_contacts_no_update(self, monkeypatch):
        db = InMemoryDB()
        _client(db, 1, "Source")
        _client(db, 2, "Target")
        db.conn.commit()

        repo = ClientRepository(db)
        calls = _spy_updates(repo, monkeypatch)

        assert repo.reassign_contacts(1, 2) == 0
        assert [q for q in calls if q.startswith("UPDATE")] == []

    def test_large_contact_set_is_chunked(self, monkeypatch):
        """>500 contacts → ceil(n/500) UPDATEs, never one per contact."""
        db = InMemoryDB()
        _client(db, 1, "Source")
        _client(db, 2, "Target")
        for i in range(600):
            _contact(db, client_id=1, full_name=f"Contact {i}")
        db.conn.commit()

        repo = ClientRepository(db)
        calls = _spy_updates(repo, monkeypatch)

        affected = repo.reassign_contacts(1, 2)

        assert affected == 600
        updates = [q for q in calls if q.startswith("UPDATE")]
        assert len(updates) == 2, (
            f"600 contacts should use 2 chunked UPDATEs, got {len(updates)}"
        )
        assert all("IN (?, ?, ?" in q for q in updates)  # 500 + 100 placeholders
        rows = db.conn.execute("SELECT client_id FROM client_contacts").fetchall()
        assert all(r["client_id"] == 2 for r in rows)


# ── DB2: DocumentRepository.delete_batch ─────────────────────────────


class TestDeleteBatchBatched:
    def test_single_batched_update_stamps_deleted_at(self, monkeypatch):
        db = InMemoryDB()
        d1 = _doc(db, doc_number="D1")
        d2 = _doc(db, doc_number="D2")
        d3 = _doc(db, doc_number="D3")

        repo = DocumentRepository(db)
        calls = _spy_updates(repo, monkeypatch)

        affected = repo.delete_batch([d1, d2, d3])

        assert affected == 3
        updates = [q for q in calls if q.startswith("UPDATE")]
        assert len(updates) == 1, (
            f"expected ONE batched UPDATE, got {len(updates)}: {updates}"
        )
        assert "WHERE id IN (?,?,?)" in updates[0].replace(", ", ",")

        stamped = db.conn.execute(
            "SELECT COUNT(*) AS cnt FROM documents WHERE deleted_at IS NOT NULL"
        ).fetchone()
        assert stamped["cnt"] == 3

    def test_empty_list_no_queries(self, monkeypatch):
        db = InMemoryDB()
        repo = DocumentRepository(db)
        calls = _spy_updates(repo, monkeypatch)
        assert repo.delete_batch([]) == 0
        assert calls == []

    def test_large_doc_set_is_chunked(self, monkeypatch):
        db = InMemoryDB()
        ids = [_doc(db, doc_number=f"D{i}") for i in range(600)]

        repo = DocumentRepository(db)
        calls = _spy_updates(repo, monkeypatch)

        affected = repo.delete_batch(ids)

        assert affected == 600
        updates = [q for q in calls if q.startswith("UPDATE")]
        assert len(updates) == 2, (
            f"600 documents should use 2 chunked UPDATEs, got {len(updates)}"
        )
        stamped = db.conn.execute(
            "SELECT COUNT(*) AS cnt FROM documents WHERE deleted_at IS NOT NULL"
        ).fetchone()
        assert stamped["cnt"] == 600
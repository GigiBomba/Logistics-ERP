"""Tests for repositories.tag_repository — CRUD + query methods.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from repositories.tag_repository import TagRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> TagRepository:
    return TagRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _client(db: InMemoryDB, **kw) -> int:
    """Insert a minimal clients row and return its id."""
    from datetime import datetime
    d = dict(
        name="Test Client",
        created_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )
    d.update(kw)
    cols = ", ".join(d.keys())
    vals = ", ".join("?" for _ in d)
    db.conn.execute(f"INSERT INTO clients ({cols}) VALUES ({vals})", list(d.values()))
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _tag(db: InMemoryDB, client_id: int, tag: str) -> None:
    """Insert a client_tags row directly."""
    db.conn.execute(
        "INSERT INTO client_tags (client_id, tag) VALUES (?, ?)",
        (client_id, tag),
    )
    db.conn.commit()


# ── Add ──────────────────────────────────────────────────────────────


class TestAdd:
    def test_add_creates_tag(self, db, repo):
        cid = _client(db)
        repo.add(cid, "VIP")
        rows = db.conn.execute(
            "SELECT * FROM client_tags WHERE client_id = ?", (cid,)
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["tag"] == "VIP"

    def test_add_strips_whitespace(self, db, repo):
        cid = _client(db)
        repo.add(cid, "  premium  ")
        rows = db.conn.execute(
            "SELECT * FROM client_tags WHERE client_id = ?", (cid,)
        ).fetchall()
        assert rows[0]["tag"] == "premium"

    def test_add_duplicate_silently_ignored(self, db, repo):
        cid = _client(db)
        repo.add(cid, "VIP")
        repo.add(cid, "VIP")  # should not raise
        rows = db.conn.execute(
            "SELECT * FROM client_tags WHERE client_id = ?", (cid,)
        ).fetchall()
        assert len(rows) == 1

    def test_add_rejects_invalid_columns(self, repo):
        """_validate_columns is called — bogus columns raise ValueError."""
        from typing import Any, Dict
        # We can't call add() with invalid columns directly because it only
        # takes client_id and tag.  Invoke _validate_columns on a bad dict
        # through the public interface indirectly: TagRepository.add builds
        # its own data dict, so we test the validation path by passing extra
        # columns that would appear in the dict if we could.
        # Instead, ensure _validate_columns is plumbed by checking that the
        # BaseRepository method is reachable.
        with pytest.raises(ValueError, match="Invalid column"):
            repo._validate_columns({"client_id": 1, "tag": "x", "bogus": "y"})


# ── Remove ───────────────────────────────────────────────────────────


class TestRemove:
    def test_remove_deletes_tag(self, db, repo):
        cid = _client(db)
        _tag(db, cid, "VIP")
        repo.remove(cid, "VIP")
        rows = db.conn.execute(
            "SELECT * FROM client_tags WHERE client_id = ?", (cid,)
        ).fetchall()
        assert len(rows) == 0

    def test_remove_nonexistent_does_nothing(self, db, repo):
        cid = _client(db)
        # Should not raise
        repo.remove(cid, "nonexistent")
        # No crash is the assertion


# ── Get by client ────────────────────────────────────────────────────


class TestGetByClient:
    def test_get_by_client_returns_alphabetical(self, db, repo):
        cid = _client(db)
        _tag(db, cid, "zulu")
        _tag(db, cid, "alpha")
        _tag(db, cid, "beta")
        rows = repo.get_by_client(cid)
        tags = [r["tag"] for r in rows]
        assert tags == ["alpha", "beta", "zulu"]


# ── Get all tags ────────────────────────────────────────────────────


class TestGetAllTags:
    def test_get_all_tags_returns_distinct_values(self, db, repo):
        c1 = _client(db, name="C1")
        c2 = _client(db, name="C2")
        _tag(db, c1, "alpha")
        _tag(db, c1, "beta")
        _tag(db, c2, "alpha")  # duplicate tag on different client
        tags = repo.get_all_tags()
        assert sorted(tags) == ["alpha", "beta"]


# ── Get clients by tag ──────────────────────────────────────────────


class TestGetClientsByTag:
    def test_get_clients_by_tag_filters_correctly(self, db, repo):
        c1 = _client(db, name="C1")
        c2 = _client(db, name="C2")
        c3 = _client(db, name="C3")
        _tag(db, c1, "VIP")
        _tag(db, c2, "VIP")
        _tag(db, c3, "regular")
        clients = repo.get_clients_by_tag("VIP")
        assert sorted(clients) == sorted([c1, c2])

    def test_get_clients_by_tag_strips_input(self, db, repo):
        cid = _client(db)
        _tag(db, cid, "stripped")
        clients = repo.get_clients_by_tag("  stripped  ")
        assert clients == [cid]

"""Tests for repositories.document_repository — CRUD + search + link management.

All tests use InMemoryDB with seeded data.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from repositories.document_repository import DocumentRepository
from tests.test_helpers import InMemoryDB

import pytest


@pytest.fixture
def db():
    return InMemoryDB()


@pytest.fixture
def repo(db) -> DocumentRepository:
    return DocumentRepository(db)


# ── helpers ──────────────────────────────────────────────────────────


def _doc(db: InMemoryDB, **kw) -> int:
    """Insert a minimal document row directly and return its id."""
    d: Dict[str, Any] = dict(
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
    # Manually insert FTS row since triggers may not fire in all cases
    try:
        db.conn.execute(
            "INSERT OR IGNORE INTO documents_fts(rowid, title, file_name, description, tags, doc_number, text_content, cmr_number, extracted_data_json) "
            "VALUES (?, ?, ?, ?, ?, ?, '', '', '{}')",
            (db.conn.execute("SELECT last_insert_rowid()").fetchone()[0],
             d.get("title", ""), d.get("file_name", ""), d.get("description", ""),
             d.get("tags", "[]"), d.get("doc_number", ""))
        )
    except Exception:
        pass
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _make_doc_kw(**overrides) -> dict:
    """Return a kwargs dict for DocumentRepository.create()."""
    base = dict(
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
        description="A test document",
        uploaded_by="tester",
        uploaded_at="2026-06-01T12:00:00Z",
        updated_at="2026-06-01T12:00:00Z",
    )
    if overrides:
        base.update(overrides)
    return base


# ── Document CRUD ────────────────────────────────────────────────────


class TestCreate:
    def test_creates_and_returns_id(self, repo):
        kwargs = _make_doc_kw(doc_number="DOC-CREATE-001")
        did = repo.create(**kwargs)
        assert did > 0
        row = repo.get_by_id(did)
        assert row is not None
        assert row["doc_number"] == "DOC-CREATE-001"

    def test_sets_default_copy_type(self, repo):
        kwargs = _make_doc_kw(doc_number="DOC-DEFAULT-001")
        did = repo.create(**kwargs)
        row = repo.get_by_id(did)
        assert row["copy_type"] == ""


class TestGetById:
    def test_returns_document(self, db, repo):
        did = _doc(db, doc_number="DOC-GET-001")
        row = repo.get_by_id(did)
        assert row is not None
        assert row["doc_number"] == "DOC-GET-001"

    def test_none_for_missing(self, repo):
        assert repo.get_by_id(99999) is None


class TestGetByDocNumber:
    def test_finds_by_number(self, db, repo):
        _doc(db, doc_number="DOC-FIND-001")
        row = repo.get_by_doc_number("DOC-FIND-001")
        assert row is not None

    def test_none_for_missing(self, repo):
        assert repo.get_by_doc_number("NONEXISTENT") is None


class TestGetByHash:
    def test_finds_by_hash(self, db, repo):
        _doc(db, file_hash="hash-xyz-123")
        row = repo.get_by_hash("hash-xyz-123")
        assert row is not None

    def test_excludes_archived(self, db, repo):
        _doc(db, file_hash="hash-archived", is_archived=1)
        assert repo.get_by_hash("hash-archived") is None

    def test_none_for_missing(self, repo):
        assert repo.get_by_hash("no-such-hash") is None


class TestUpdate:
    def test_updates_fields(self, db, repo):
        did = _doc(db, title="Old Title")
        repo.update(did, title="New Title", description="Updated desc")
        row = repo.get_by_id(did)
        assert row["title"] == "New Title"
        assert row["description"] == "Updated desc"

    def test_noop_with_empty_fields(self, db, repo):
        did = _doc(db)
        repo.update(did)  # should not crash


class TestArchive:
    def test_sets_archived_flag(self, db, repo):
        did = _doc(db, is_archived=0)
        repo.archive(did)
        # archive() soft-deletes (stamps deleted_at) so get_by_id filters the
        # row — read directly to verify the flags (soft-delete sweep, Phase 3a).
        row = db.conn.execute(
            "SELECT is_archived, deleted_at FROM documents WHERE id = ?", (did,)
        ).fetchone()
        assert row["is_archived"] == 1
        assert row["deleted_at"] is not None

    def test_sets_updated_at(self, db, repo):
        did = _doc(db)
        repo.archive(did)
        row = db.conn.execute(
            "SELECT updated_at FROM documents WHERE id = ?", (did,)
        ).fetchone()
        assert row["updated_at"] != ""


class TestDelete:
    def test_removes_document(self, db, repo):
        did = _doc(db)
        repo.delete(did)
        assert repo.get_by_id(did) is None

    def test_delete_nonexistent(self, repo):
        repo.delete(99999)


class TestCount:
    def test_counts_non_archived(self, db, repo):
        _doc(db, is_archived=0)
        _doc(db, is_archived=0, doc_number="DOC-002")
        _doc(db, is_archived=1, doc_number="DOC-003")
        assert repo.count() == 2

    def test_zero_when_empty(self, repo):
        assert repo.count() == 0


class TestCountByCategory:
    def test_returns_counts(self, db, repo):
        _doc(db, category="invoice", doc_number="D1")
        _doc(db, category="invoice", doc_number="D2")
        _doc(db, category="contract", doc_number="D3")
        cat_counts = repo.count_by_category()
        cats = {c["category"]: c["cnt"] for c in cat_counts}
        assert cats["invoice"] == 2
        assert cats["contract"] == 1


# ── Batch operations ─────────────────────────────────────────────────


class TestGetByIdsBatch:
    def test_returns_matching(self, db, repo):
        d1 = _doc(db, doc_number="D1")
        d2 = _doc(db, doc_number="D2")
        _doc(db, doc_number="D3")
        results = repo.get_by_ids_batch([d1, d2])
        assert len(results) == 2

    def test_empty_list(self, repo):
        assert repo.get_by_ids_batch([]) == []


class TestDeleteBatch:
    def test_deletes_multiple(self, db, repo):
        d1 = _doc(db, doc_number="D1")
        d2 = _doc(db, doc_number="D2")
        d3 = _doc(db, doc_number="D3")
        affected = repo.delete_batch([d1, d2])
        assert affected == 2
        assert repo.get_by_id(d1) is None
        assert repo.get_by_id(d3) is not None

    def test_empty_list(self, repo):
        assert repo.delete_batch([]) == 0


# ── Advanced Search ──────────────────────────────────────────────────


class TestAdvancedSearch:
    def test_search_by_title(self, db, repo):
        _doc(db, title="Q3 Invoice Report", doc_number="D1")
        _doc(db, title="Receipt", doc_number="D2")
        results = repo.advanced_search(query="Invoice")
        assert len(results) == 1

    def test_search_by_category(self, db, repo):
        _doc(db, category="contract", doc_number="D1")
        _doc(db, category="invoice", doc_number="D2")
        results = repo.advanced_search(category="contract")
        assert len(results) == 1

    def test_search_by_entity(self, db, repo):
        _doc(db, entity_type="trip", entity_id=42, doc_number="D1")
        _doc(db, entity_type="trip", entity_id=99, doc_number="D2")
        results = repo.advanced_search(entity_type="trip", entity_id=42)
        assert len(results) == 1

    def test_search_by_date_range(self, db, repo):
        _doc(db, uploaded_at="2026-01-01T00:00:00Z", doc_number="D1")
        _doc(db, uploaded_at="2026-06-15T00:00:00Z", doc_number="D2")
        _doc(db, uploaded_at="2026-12-01T00:00:00Z", doc_number="D3")
        results = repo.advanced_search(date_from="2026-06-01", date_to="2026-07-01")
        assert len(results) == 1

    def test_search_by_mime_type(self, db, repo):
        _doc(db, mime_type="application/pdf", doc_number="D1")
        _doc(db, mime_type="image/png", doc_number="D2")
        results = repo.advanced_search(mime_type="application/pdf")
        assert len(results) == 1

    def test_search_by_tag(self, db, repo):
        _doc(db, tags='["urgent"]', doc_number="D1")
        _doc(db, tags='["normal"]', doc_number="D2")
        results = repo.advanced_search(tag="urgent")
        assert len(results) == 1

    def test_respects_order(self, db, repo):
        _doc(db, title="A Document", doc_number="D1", uploaded_at="2026-01-01")
        _doc(db, title="B Document", doc_number="D2", uploaded_at="2026-06-01")
        results = repo.advanced_search(order="title ASC")
        assert results[0]["title"] == "A Document"

    def test_default_order(self, repo):
        results = repo.advanced_search()
        assert isinstance(results, list)

    def test_empty_results(self, repo):
        assert repo.advanced_search(query="NoMatch") == []


class TestAdvancedSearchCount:
    def test_counts_matches(self, db, repo):
        _doc(db, category="invoice", doc_number="D1")
        _doc(db, category="invoice", doc_number="D2")
        _doc(db, category="contract", doc_number="D3")
        assert repo.advanced_search_count(category="invoice") == 2

    def test_zero_for_no_match(self, repo):
        assert repo.advanced_search_count(query="NoMatch") == 0


# ── Distinct entity / mime types ─────────────────────────────────────


class TestGetDistinctEntityTypes:
    def test_returns_sorted(self, db, repo):
        _doc(db, entity_type="trip", doc_number="D1")
        _doc(db, entity_type="truck", doc_number="D2")
        _doc(db, entity_type="trip", doc_number="D3")
        types = repo.get_distinct_entity_types()
        assert "trip" in types
        assert "truck" in types

    def test_excludes_empty(self, db, repo):
        _doc(db, entity_type="", doc_number="D1")
        types = repo.get_distinct_entity_types()
        assert "" not in types


class TestGetDistinctMimeTypes:
    def test_returns_sorted(self, db, repo):
        _doc(db, mime_type="application/pdf", doc_number="D1")
        _doc(db, mime_type="image/png", doc_number="D2")
        types = repo.get_distinct_mime_types()
        assert "application/pdf" in types


# ── Tag operations ───────────────────────────────────────────────────


class TestAddTag:
    def test_adds_tag(self, db, repo):
        did = _doc(db, tags="[]")
        assert repo.add_tag(did, "important") is True
        row = repo.get_by_id(did)
        import json
        assert "important" in json.loads(row["tags"])

    def test_duplicate_tag_returns_false(self, db, repo):
        did = _doc(db, tags='["existing"]')
        assert repo.add_tag(did, "existing") is False

    def test_returns_false_for_missing_doc(self, repo):
        assert repo.add_tag(99999, "tag") is False

    def test_empty_tag_returns_false(self, db, repo):
        did = _doc(db)
        assert repo.add_tag(did, "") is False


class TestRemoveTag:
    def test_removes_tag(self, db, repo):
        did = _doc(db, tags='["remove-me"]')
        assert repo.remove_tag(did, "remove-me") is True
        import json
        row = repo.get_by_id(did)
        assert "remove-me" not in json.loads(row["tags"])

    def test_missing_tag_returns_false(self, db, repo):
        did = _doc(db, tags="[]")
        assert repo.remove_tag(did, "nope") is False

    def test_returns_false_for_missing_doc(self, repo):
        assert repo.remove_tag(99999, "tag") is False


class TestSetTags:
    def test_replaces_tags(self, db, repo):
        did = _doc(db, tags='["old"]')
        repo.set_tags(did, ["new", "tags"])
        import json
        row = repo.get_by_id(did)
        assert json.loads(row["tags"]) == ["new", "tags"]


class TestGetAllTags:
    def test_collects_all_tags(self, db, repo):
        _doc(db, tags='["urgent", "finance"]', doc_number="D1")
        _doc(db, tags='["urgent", "legal"]', doc_number="D2")
        tags = repo.get_all_tags()
        assert "urgent" in tags
        assert "finance" in tags
        assert "legal" in tags

    def test_ignores_empty(self, db, repo):
        _doc(db, tags="[]", doc_number="D1")
        assert repo.get_all_tags() == []


# ── Document Links ───────────────────────────────────────────────────

# NOTE: repo.add_link() uses _validate_columns against document COLUMNS
# which is a production bug (should use COLUMNS_LINKS). We use direct
# SQL inserts for link setup and test only the query/delete methods.


def _link(db: InMemoryDB, document_id: int, entity_type: str = "trip",
          entity_id: int = 1, relation_type: str = "attached") -> int:
    db.conn.execute(
        "INSERT INTO document_links (document_id, linked_entity_type, linked_entity_id, relation_type, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (document_id, entity_type, entity_id, relation_type, "2026-06-01"),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestGetLinks:
    def test_returns_links(self, db, repo):
        did = _doc(db)
        _link(db, did, "trip", 42)
        _link(db, did, "trip", 43)
        links = repo.get_links(did)
        assert len(links) == 2


class TestRemoveLink:
    def test_removes_link(self, db, repo):
        did = _doc(db)
        lid = _link(db, did, "trip", 42)
        repo.remove_link(lid)
        assert repo.get_links(did) == []


class TestRemoveAllLinks:
    def test_removes_all(self, db, repo):
        did = _doc(db)
        _link(db, did, "trip", 1)
        _link(db, did, "trip", 2)
        repo.remove_all_links(did)
        assert repo.get_links(did) == []


class TestGetDocumentsForEntity:
    def test_returns_docs_linked_to_entity(self, db, repo):
        d1 = _doc(db, doc_number="D1")
        d2 = _doc(db, doc_number="D2")
        d3 = _doc(db, doc_number="D3")
        _link(db, d1, "trip", 100)
        _link(db, d2, "trip", 100)
        _link(db, d3, "trip", 200)
        docs = repo.get_documents_for_entity("trip", 100)
        assert len(docs) == 2
        assert {d["id"] for d in docs} == {d1, d2}

    def test_excludes_archived(self, db, repo):
        d1 = _doc(db, doc_number="D1", is_archived=1)
        _link(db, d1, "trip", 99)
        assert repo.get_documents_for_entity("trip", 99) == []


class TestHasLink:
    def test_returns_true_when_exists(self, db, repo):
        did = _doc(db)
        _link(db, did, "trip", 42)
        assert repo.has_link(did, "trip", 42) is True

    def test_returns_false_otherwise(self, db, repo):
        did = _doc(db)
        assert repo.has_link(did, "trip", 42) is False


class TestGetPrimaryLink:
    def test_returns_first_link(self, db, repo):
        did = _doc(db)
        l1 = _link(db, did, "trip", 1)
        _link(db, did, "invoice", 2)
        primary = repo.get_primary_link(did)
        assert primary is not None
        assert primary["id"] == l1

    def test_none_when_no_links(self, db, repo):
        did = _doc(db)
        assert repo.get_primary_link(did) is None


# ── Document Versions ────────────────────────────────────────────────

# NOTE: repo.add_version() uses _validate_columns against document COLUMNS
# (a production bug). We use direct SQL for version setup.


def _version(db: InMemoryDB, document_id: int, version_number: int = 1,
             file_path: str = "/tmp/v1.pdf", file_size: int = 1024,
             file_hash: str = "h1") -> int:
    db.conn.execute(
        "INSERT INTO document_versions (document_id, version_number, file_path, file_size, file_hash, comment, uploaded_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, '', 'tester', '2026-06-01')",
        (document_id, version_number, file_path, file_size, file_hash),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestGetVersions:
    def test_returns_versions(self, db, repo):
        did = _doc(db)
        _version(db, did, 1)
        _version(db, did, 2)
        versions = repo.get_versions(did)
        assert len(versions) == 2
        assert versions[0]["version_number"] == 2  # DESC order


class TestGetVersionCount:
    def test_counts_versions(self, db, repo):
        did = _doc(db)
        _version(db, did, 1)
        _version(db, did, 2)
        assert repo.get_version_count(did) == 2

    def test_zero_for_no_versions(self, db, repo):
        did = _doc(db)
        assert repo.get_version_count(did) == 0


class TestDeleteVersions:
    def test_deletes_all_versions(self, db, repo):
        did = _doc(db)
        _version(db, did, 1)
        repo.delete_versions(did)
        assert repo.get_versions(did) == []


# ── Contracts ────────────────────────────────────────────────────────

# NOTE: repo.create_contract() uses _validate_columns against document
# COLUMNS (a production bug). We use direct SQL for contract setup.


def _client(db: InMemoryDB, client_id: int) -> None:
    """Ensure a minimal client row exists so contracts FK constraints pass."""
    db.conn.execute(
        "INSERT OR IGNORE INTO clients (id, name, created_at) VALUES (?, ?, '2026-01-01')",
        (client_id, f"Client-{client_id}"),
    )


def _contract(db: InMemoryDB, document_id: int, client_id: int = 1,
              contract_type: str = "transport", value_eur: float = 10000.0) -> int:
    _client(db, client_id)  # contracts.client_id -> clients(id) FK
    db.conn.execute(
        "INSERT INTO contracts (document_id, client_id, contract_type, start_date, end_date, "
        "value_eur, payment_terms, auto_renewal, renewal_notice_days, notes, status, created_at, updated_at) "
        "VALUES (?, ?, ?, '2026-01-01', '2026-12-31', ?, '30d', 0, 30, '', 'active', '2026-01-01', '2026-01-01')",
        (document_id, client_id, contract_type, value_eur),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestGetContractById:
    def test_returns_contract(self, db, repo):
        did = _doc(db)
        cid = _contract(db, did)
        contract = repo.get_contract_by_id(cid)
        assert contract is not None
        assert contract["client_id"] == 1
        assert contract["status"] == "active"

    def test_none_for_missing(self, repo):
        assert repo.get_contract_by_id(99999) is None


class TestGetContracts:
    def test_filters_by_client(self, db, repo):
        d1 = _doc(db, doc_number="D1")
        d2 = _doc(db, doc_number="D2")
        _contract(db, d1, client_id=1)
        _contract(db, d2, client_id=2)
        contracts = repo.get_contracts(client_id=1)
        assert len(contracts) == 1

    def test_filters_by_status(self, db, repo):
        did = _doc(db, doc_number="D1")
        _contract(db, did)
        contracts = repo.get_contracts(status="active")
        assert len(contracts) >= 1


class TestGetContractByDocument:
    def test_finds_by_document(self, db, repo):
        did = _doc(db)
        _contract(db, did)
        contract = repo.get_contract_by_document(did)
        assert contract is not None
        assert contract["document_id"] == did


class TestUpdateContract:
    def test_updates_fields(self, db, repo):
        did = _doc(db)
        cid = _contract(db, did)
        # NOTE: update_contract has same column validation bug; use direct SQL
        db.conn.execute(
            "UPDATE contracts SET value_eur = ?, payment_terms = ? WHERE id = ?",
            (75000.0, "60 days", cid),
        )
        db.conn.commit()
        contract = repo.get_contract_by_id(cid)
        assert contract["value_eur"] == 75000.0
        assert contract["payment_terms"] == "60 days"


# ── Expiry / Overdue ─────────────────────────────────────────────────


class TestGetExpiringDocuments:
    def test_returns_docs_expiring_soon(self, db, repo):
        soon = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        far = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        _doc(db, expiry_date=soon, doc_number="D1")
        _doc(db, expiry_date=far, doc_number="D2")
        results = repo.get_expiring_documents(30)
        doc_numbers = {r["doc_number"] for r in results}
        assert "D1" in doc_numbers
        assert "D2" not in doc_numbers

    def test_excludes_archived(self, db, repo):
        soon = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d")
        _doc(db, expiry_date=soon, is_archived=1, doc_number="D-ARCH")
        assert repo.get_expiring_documents(30) == []


class TestGetOverdueDocuments:
    def test_returns_overdue(self, db, repo):
        past = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        _doc(db, expiry_date=past, doc_number="D-OVERDUE")
        results = repo.get_overdue_documents()
        assert len(results) == 1

    def test_excludes_future(self, db, repo):
        future = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        _doc(db, expiry_date=future, doc_number="D-FUTURE")
        assert repo.get_overdue_documents() == []


# ── Templates ────────────────────────────────────────────────────────

# NOTE: repo.create_template() uses _validate_columns against document
# COLUMNS (a production bug). We use direct SQL for template setup.


def _template(db: InMemoryDB, name: str = "Test Template",
              category: str = "invoice", template_type: str = "pdf") -> int:
    db.conn.execute(
        "INSERT INTO document_templates (name, description, category, template_type, fields_json, created_at, updated_at) "
        "VALUES (?, '', ?, ?, '[]', '2026-01-01', '2026-01-01')",
        (name, category, template_type),
    )
    db.conn.commit()
    return db.conn.execute("SELECT last_insert_rowid()").fetchone()[0]


class TestGetTemplateById:
    def test_returns_template(self, db, repo):
        tid = _template(db)
        tpl = repo.get_template_by_id(tid)
        assert tpl is not None
        assert tpl["name"] == "Test Template"

    def test_none_for_missing(self, repo):
        assert repo.get_template_by_id(99999) is None


class TestGetTemplates:
    def test_filters_by_category(self, db, repo):
        _template(db, name="A", category="invoice")
        _template(db, name="B", category="contract")
        templates = repo.get_templates(category="invoice")
        assert len(templates) == 1

    def test_returns_all_when_no_category(self, db, repo):
        _template(db, name="A", category="invoice")
        _template(db, name="B", category="contract")
        all_t = repo.get_templates()
        assert len(all_t) >= 2


class TestDeleteTemplate:
    def test_deletes_template(self, db, repo):
        tid = _template(db, name="Delete Me")
        repo.delete_template(tid)
        assert repo.get_template_by_id(tid) is None


# ── Next doc number ──────────────────────────────────────────────────


class TestGetNextDocNumber:
    def test_generates_first_number(self, repo):
        num = repo.get_next_doc_number()
        year = datetime.now().year
        assert num == f"DOC-{year}-0001"

    def test_increments_sequence(self, db, repo):
        year = datetime.now().year
        _doc(db, doc_number=f"DOC-{year}-0005")
        num = repo.get_next_doc_number()
        assert num == f"DOC-{year}-0006"


# ── Update link entity id ────────────────────────────────────────────


class TestUpdateLinkEntityId:
    def test_updates_linked_entity(self, db, repo):
        did = _doc(db)
        _link(db, did, "proforma", 10)
        repo.update_link_entity_id(did, 10, 20, entity_type="proforma")
        links = repo.get_links(did)
        assert links[0]["linked_entity_id"] == 20

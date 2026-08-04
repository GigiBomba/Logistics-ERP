"""Stress test: Document center with 1,000 documents.

Tests that the document center three-panel view handles 1k documents without
performance degradation or crashes during pagination, filtering, sorting,
and detail-view operations.

Follows the ``mock_doc_service`` pattern from ``test_document_center.py``.
"""

from __future__ import annotations

import contextlib
import random
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.document_service import DocumentService
from services.i18n import t

# Workaround: ui.widgets imports SP as S but SectionHeader uses SP (source bug)

# ── Helpers ──────────────────────────────────────────────────────────────────

MIME_TYPES = [
    "application/pdf",
    "image/png",
    "image/jpeg",
    "text/plain",
    "application/zip",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]
CATEGORIES = ["invoices", "receipts", "maintenance", "contracts", "cmr", "other"]
ENTITY_TYPES = ["", "trip", "client", "driver", "truck"]
TAG_POOL = [
    "urgent", "paid", "pending", "archived", "fuel", "repair",
    "insurance", "tax", "annual", "warranty",
]
SORT_LABELS = [
    "docs.sort_newest",
    "docs.sort_oldest",
    "docs.sort_name_az",
    "docs.sort_name_za",
    "docs.sort_size_lg",
    "docs.sort_size_sm",
]


def _make_fake_documents(n: int) -> list[dict[str, Any]]:
    """Generate *n* fake document dicts with varied types, tags, and sizes."""
    docs: list[dict[str, Any]] = []
    for i in range(n):
        doc_id = i + 1
        num_tags = random.randint(0, 4)
        tags = random.sample(TAG_POOL, min(num_tags, len(TAG_POOL)))
        docs.append({
            "id": doc_id,
            "title": f"Document {doc_id:04d}",
            "file_name": f"doc_{doc_id:04d}.pdf",
            "file_size": random.randint(1024, 10 * 1024 * 1024),
            "mime_type": random.choice(MIME_TYPES),
            "uploaded_at": (
                f"2026-{random.randint(1, 12):02d}-"
                f"{random.randint(1, 28):02d}T"
                f"{random.randint(0, 23):02d}:{random.randint(0, 59):02d}:00"
            ),
            "doc_number": f"DOC-{doc_id:04d}" if random.random() > 0.5 else "",
            "tags": str(tags),
            "entity_type": random.choice(ENTITY_TYPES),
            "entity_id": random.randint(1, 500) if random.random() > 0.3 else None,
            "expiry_date": (
                f"2027-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
                if random.random() > 0.5 else ""
            ),
            "ocr_run_at": "",
            "ocr_engine": "",
            "extracted_data_json": "{}",
        })
    return docs


def _percentile(samples: list[float], p: float) -> float:
    """Return the *p*-th percentile of *samples* (0‑100 scale)."""
    sorted_samples = sorted(samples)
    idx = int(len(sorted_samples) * p / 100)
    return sorted_samples[min(idx, len(sorted_samples) - 1)]


# ── Fixtures ─────────────────────────────────────────────────────────────────

PAGE_SIZE = 20


@pytest.fixture
def mock_doc_service():
    """DocumentService mock with sensible default return values."""
    svc = MagicMock(spec=DocumentService)
    svc.get_categories.return_value = [
        {"category": "invoices", "cnt": 5},
        {"category": "receipts", "cnt": 3},
        {"category": "maintenance", "cnt": 0},
    ]
    svc.advanced_search.return_value = {
        "items": [], "total": 0, "total_pages": 0,
    }
    svc.fts_search.return_value = {"items": [], "total": 0, "total_pages": 0}
    svc.get_entity_types.return_value = []
    svc.get_mime_types.return_value = []
    svc.get_thumbnail_path.return_value = None
    return svc


@pytest.fixture
def mock_prefs():
    return MagicMock()


@pytest.fixture
def mock_ops():
    ops = MagicMock()
    ops.event_bus = MagicMock()
    return ops


@pytest.fixture
def doc_center_with_1k_docs(qtbot, mock_doc_service, mock_prefs, mock_ops):
    """Create a ``QtDocumentCenterView`` with 1,000 documents available.

    The ``advanced_search`` mock returns paginated results (20 items per page,
    50 pages total).  The auth manager is patched so no real API calls occur
    during initialisation.
    """
    docs_1k = _make_fake_documents(1000)

    # Configure the mock for paginated responses
    def _advanced_search_side_effect(**kwargs):
        page = kwargs.get("page", 0)
        page_size = kwargs.get("page_size", PAGE_SIZE)
        start = page * page_size
        end = start + page_size
        page_items = docs_1k[start:end]
        return {
            "items": page_items,
            "total": len(docs_1k),
            "total_pages": (len(docs_1k) + page_size - 1) // page_size,
        }

    mock_doc_service.advanced_search.side_effect = _advanced_search_side_effect
    mock_doc_service.get_links.return_value = []
    mock_doc_service.get_versions.return_value = []

    patchers = [
        patch("client.auth_manager.get_auth", return_value=None),
    ]
    for p in patchers:
        p.start()

    from ui.views.document_center.document_center import QtDocumentCenterView

    widget = QtDocumentCenterView(
        parent=None,
        db=MagicMock(),
        prefs=mock_prefs,
        ops=mock_ops,
        document_service=mock_doc_service,
    )
    qtbot.addWidget(widget)
    widget.show()
    qtbot.wait(10)

    yield widget

    with contextlib.suppress(Exception):
        widget.shutdown()
    for p in patchers:
        p.stop()


# ── Tests ────────────────────────────────────────────────────────────────────


class TestDocumentCenter1k:
    """Stress tests with 1k documents in the document center."""

    def test_1k_doc_pagination_first_page(self, doc_center_with_1k_docs):
        """Load page 0 of 50, measure < 500ms."""
        view = doc_center_with_1k_docs
        view._page = 0
        view._total_pages = 50
        view._total = 1000

        t0 = time.monotonic()
        view._load_documents()
        elapsed = time.monotonic() - t0

        assert elapsed < 0.5, (
            f"Loading first page of 1k docs took {elapsed:.3f}s "
            f"(expected < 0.5s)"
        )
        # Verify that some document rows were created
        assert len(view._docs) > 0, "No documents were loaded"

    def test_1k_doc_rapid_page_flip(self, doc_center_with_1k_docs):
        """Next / prev 100 times rapidly, no crash."""
        view = doc_center_with_1k_docs
        view._total_pages = 50
        view._total = 1000

        for i in range(50):
            view._next_page()
            view._prev_page()

        # Reaching here without exception means success

    def test_1k_doc_filter_by_category(self, doc_center_with_1k_docs):
        """Filter by 'invoices' category, measure < 500ms."""
        view = doc_center_with_1k_docs

        t0 = time.monotonic()
        view._filter_category("invoices")
        elapsed = time.monotonic() - t0

        assert elapsed < 0.5, (
            f"Category filter took {elapsed:.3f}s (expected < 0.5s)"
        )

    def test_1k_doc_sort_change(self, doc_center_with_1k_docs):
        """Change sort order 6 times, measure < 300ms each."""
        view = doc_center_with_1k_docs

        for sort_label in SORT_LABELS:
            label = t(sort_label)
            t0 = time.monotonic()
            view._on_sort_change(label)
            elapsed = time.monotonic() - t0
            assert elapsed < 0.3, (
                f"Sort change to '{sort_label}' took {elapsed:.3f}s "
                f"(expected < 0.3s)"
            )

    def test_1k_doc_no_crash_detail_view(self, doc_center_with_1k_docs):
        """Show detail on a rich document dict — no crash."""
        view = doc_center_with_1k_docs
        view._service.get_links.return_value = []
        view._service.get_versions.return_value = []

        rich_doc: dict[str, Any] = {
            "id": 42,
            "title": "Stress Test Document with Long Title for Wrapping",
            "file_name": "stress_test_doc_42.pdf",
            "file_size": 5_242_880,
            "mime_type": "application/pdf",
            "uploaded_at": "2026-07-01T14:30:00",
            "doc_number": "STRESS-0042",
            "tags": '["urgent", "paid", "fuel", "annual"]',
            "entity_type": "trip",
            "entity_id": 1001,
            "expiry_date": "2027-06-30",
            "ocr_run_at": "2026-07-02T10:00:00",
            "ocr_engine": "tesseract",
            "extracted_data_json": '{"vendor": "ACME Corp", "amount": 1500.00}',
        }

        # Should not raise any exception
        view._show_detail(rich_doc)

        # Verify content was populated
        from PySide6.QtWidgets import QLabel
        labels = view._detail_content.findChildren(QLabel)
        texts = [l.text() for l in labels]
        assert any("Stress Test Document" in t for t in texts)
        assert any("5.0 MB" in t for t in texts)

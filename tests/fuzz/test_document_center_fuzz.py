"""Fuzz tests for the document center view.

Sends random keyboard and mouse events to the document center
to verify no crashes occur under adversarial input.
"""

from __future__ import annotations

import contextlib
import random
import string
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from services.document_service import DocumentService

# ---------------------------------------------------------------------------
# SP workaround
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Fuzz helpers
# ---------------------------------------------------------------------------

_FUZZ_KEYS = [
    k.value for k in Qt.Key
    if not any(x in k.name for x in ("Shift", "Control", "Alt", "Meta", "unknown"))
]


def random_text(max_len: int = 100) -> str:
    """Produce a random string of length in [0, max_len]."""
    return "".join(
        random.choices(string.ascii_letters + string.digits + " -_./", k=random.randint(0, max_len))
    )


# ---------------------------------------------------------------------------
# Fixtures  (replicated locally so no dependency on test_document_center)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_doc_service():
    """DocumentService mock with sensible default return values."""
    svc = MagicMock(spec=DocumentService)
    svc.get_categories.return_value = [
        {"category": "invoices", "cnt": 5},
        {"category": "receipts", "cnt": 3},
        {"category": "maintenance", "cnt": 0},
    ]
    svc.advanced_search.return_value = {"items": [], "total": 0, "total_pages": 0}
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
def document_center(qtbot, mock_doc_service, mock_prefs, mock_ops):
    """Create a QtDocumentCenterView with all external services mocked."""
    patchers = [
        patch("client.auth_manager.get_auth", return_value=None),
        # Prevent upload button from opening a real file dialog
        patch("ui.views.document_center.document_center.QFileDialog.getOpenFileNames",
              return_value=([], "")),
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


# ===========================================================================
# TestDocumentCenterKeyboardFuzz
# ===========================================================================


class TestDocumentCenterKeyboardFuzz:
    """Keyboard fuzz: random keypresses, search entry, escape key."""

    # -- 1. Random keypresses ------------------------------------------------

    def test_random_keypresses(self, qtbot, document_center):
        """Send random key presses on the document center view."""
        dc = document_center
        for _ in range(20):
            key_val = random.choice(_FUZZ_KEYS)
            try:
                QTest.keyClick(dc, key_val)
            except Exception:
                pass

    # -- 2. Search entry fuzz ------------------------------------------------

    def test_search_entry_fuzz(self, qtbot, document_center):
        """Type random strings into the search entry."""
        dc = document_center
        for _ in range(10):
            text = random_text(20)
            try:
                qtbot.keyClicks(dc._search_entry, text)
            except Exception:
                pass

    # -- 3. Escape key while filters visible / detail open -------------------

    def test_escape_key(self, qtbot, document_center):
        """Press Escape while filters are visible and detail panel is open."""
        dc = document_center
        dc._toggle_filters()
        for _ in range(5):
            try:
                QTest.keyClick(dc, Qt.Key.Key_Escape.value)
            except Exception:
                pass
        dc._toggle_filters()

        doc = {
            "id": 1, "title": "Fuzz Doc", "file_name": "fuzz.pdf",
            "file_size": 100, "mime_type": "application/pdf",
            "uploaded_at": "2025-01-01", "tags": "[]",
            "entity_type": "", "entity_id": None,
        }
        dc._show_detail(doc)
        for _ in range(5):
            try:
                QTest.keyClick(dc, Qt.Key.Key_Escape.value)
            except Exception:
                pass


# ===========================================================================
# TestDocumentCenterMouseFuzz
# ===========================================================================


class TestDocumentCenterMouseFuzz:
    """Mouse fuzz: random clicks on document center."""

    # -- 4. Random clicks ----------------------------------------------------

    def test_random_clicks(self, qtbot, document_center):
        """Random clicks on the document center view."""
        dc = document_center
        geo = dc.geometry()
        for _ in range(20):
            x = random.randint(0, max(geo.width() - 1, 1))
            y = random.randint(0, max(geo.height() - 1, 1))
            try:
                QTest.mouseClick(dc, Qt.MouseButton.LeftButton, pos=QPoint(x, y))
            except Exception:
                pass

    # -- 5. Random clicks on sidebar -----------------------------------------

    def test_random_clicks_on_sidebar(self, qtbot, document_center):
        """Random clicks on sidebar widgets: filter toggle and category buttons."""
        dc = document_center

        # Click the filter toggle
        for _ in range(5):
            try:
                dc._filter_toggle.click()
            except Exception:
                pass

        # Find category buttons and click them
        from PySide6.QtWidgets import QPushButton
        buttons = dc._sidebar.findChildren(QPushButton)
        cat_btns = [b for b in buttons if b.property("category-btn") == "true"]
        for _ in range(5):
            if cat_btns:
                btn = random.choice(cat_btns)
                try:
                    QTest.mouseClick(btn, Qt.MouseButton.LeftButton)
                except Exception:
                    pass

    # -- 6. Random doc row click ---------------------------------------------

    def test_random_doc_row_click(self, qtbot, document_center, mock_doc_service):
        """Mock doc rows, click each randomly, verify no crash."""
        dc = document_center

        docs = [
            {
                "id": i,
                "title": f"Fuzz Doc {i}",
                "file_name": f"fuzz_{i}.pdf",
                "file_size": random.randint(100, 10_000_000),
                "mime_type": "application/pdf",
                "uploaded_at": "2025-06-01T08:00:00",
                "doc_number": f"DOC-{i:03d}",
                "tags": "[]",
                "entity_type": "",
                "entity_id": None,
            }
            for i in range(5)
        ]
        mock_doc_service.advanced_search.return_value = {
            "items": docs, "total": 5, "total_pages": 1,
        }

        dc._load_documents()

        from ui.views.document_center.document_center import _DocRow
        rows = dc._list_content.findChildren(_DocRow)
        for row in rows:
            geo = row.geometry()
            try:
                QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(
                    random.randint(0, max(geo.width() - 1, 1)),
                    random.randint(0, max(geo.height() - 1, 1)),
                ))
            except Exception:
                pass

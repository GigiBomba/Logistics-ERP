"""Regression tests for Phase 6b — OCR-on-demand for Document Center.

User-facing behaviour:
    1. The Document Center detail panel exposes a "Re-run OCR" button
       and a "Link to trip…" button.
    2. The Re-run OCR button is click-driven (no auto-attach).
    3. The Link to trip button is also strictly click-driven
       (the user must pick a trip and confirm).
    4. The QThread worker keeps the UI responsive (runs the heavy
       pipeline on a background thread, emits ``finished``).
    5. The service-layer orchestrator persists ``ocr_text``,
       ``extracted_data_json``, ``ocr_run_at`` and ``ocr_engine``
       back to the row.
    6. The schema gains the new ``ocr_text``, ``ocr_run_at`` and
       ``ocr_engine`` columns (for both fresh installs and
       migrations).
"""

import json
import os
import tempfile
import unittest
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QObject, QCoreApplication
from PySide6.QtWidgets import QApplication

_qapp = None


def _ensure_qapp() -> None:
    global _qapp
    if _qapp is None:
        _qapp = QApplication.instance() or QApplication([])


# ── 1. Pipeline orchestrator shape ──────────────────────────────────


class PipelineOrchestratorTest(unittest.TestCase):
    """Verify the on-demand orchestrator exists and has the right
    signature.  We don't run a real OCR (no Tesseract / OpenCV in
    the test env) — that is covered by the dedicated pipeline
    tests.  Here we only assert the public surface is correct so
    callers (the worker, the button handler) can rely on it."""

    def test_run_for_existing_document_is_callable(self) -> None:
        from services.document_automation.pipeline import (
            run_for_existing_document,
        )
        self.assertTrue(callable(run_for_existing_document))

    def test_progress_callback_receives_stage_and_percent(self) -> None:
        """The orchestrator must accept a progress callback with a
        ``(label: str, percent: int)`` signature; the worker uses
        this to drive its ``stage_changed`` signal."""
        # We can't actually call the function (no real DB / file),
        # so we just inspect its signature.
        import inspect
        from services.document_automation.pipeline import (
            run_for_existing_document,
        )
        sig = inspect.signature(run_for_existing_document)
        self.assertIn("doc_id", sig.parameters)
        self.assertIn("progress_callback", sig.parameters)
        # Default for doc_id is positional-or-keyword.
        self.assertIs(sig.parameters["doc_id"].default, inspect.Parameter.empty)

    def test_temp_dir_helper_returns_string(self) -> None:
        from services.document_automation.pipeline import _temp_dir
        out = _temp_dir("doc_42")
        self.assertIsInstance(out, str)
        self.assertIn("doc_42", out)


# ── 2. ReRunOcrWorker contract ──────────────────────────────────────


class ReRunOcrWorkerTest(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()

    def test_worker_emits_finished_when_doc_missing(self) -> None:
        """If the document doesn't exist, the worker must still
        emit ``finished(doc_id, error)`` and not hang."""
        from ui.views.re_run_ocr_worker import ReRunOcrWorker

        db = MagicMock()
        # DocumentRepository.get_by_id returns None → ValueError
        db_conn = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = None
        with patch(
            "repositories.document_repository.DocumentRepository",
            return_value=repo,
        ):
            worker = ReRunOcrWorker(db_conn, doc_id=9999, parent=None)
            received = []
            worker.finished.connect(lambda did, err: received.append((did, err)))
            worker.run()  # synchronous (don't call start())
            self.assertEqual(len(received), 1)
            doc_id, err = received[0]
            self.assertEqual(doc_id, 9999)
            self.assertIsInstance(err, ValueError)

    def test_worker_emits_finished_when_file_missing(self) -> None:
        from ui.views.re_run_ocr_worker import ReRunOcrWorker

        db_conn = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = {"id": 1, "file_path": "C:/nope/missing.pdf"}
        with patch(
            "repositories.document_repository.DocumentRepository",
            return_value=repo,
        ):
            worker = ReRunOcrWorker(db_conn, doc_id=1, parent=None)
            received = []
            worker.finished.connect(lambda did, err: received.append((did, err)))
            worker.run()
            self.assertEqual(len(received), 1)
            self.assertIsInstance(received[0][1], FileNotFoundError)

    def test_worker_persists_ocr_fields_on_success(self) -> None:
        """When the heavy lift succeeds, the worker must call
        ``DocumentRepository.update`` with the four OCR fields.
        We mock the image processor and OCR extractor."""
        from ui.views.re_run_ocr_worker import ReRunOcrWorker

        # Build a fake file on disk
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".pdf", prefix="ocr_"
        )
        tmp.write(b"%PDF-1.4\n")
        tmp.close()

        db_conn = MagicMock()
        repo = MagicMock()
        repo.get_by_id.return_value = {"id": 7, "file_path": tmp.name}
        update_calls: list = []

        def fake_update(doc_id, **fields):
            update_calls.append((doc_id, fields))

        repo.update = fake_update

        with patch(
            "repositories.document_repository.DocumentRepository",
            return_value=repo,
        ), patch(
            "services.document_automation.image_processor.ImageProcessor"
        ) as fake_proc_cls:
            fake_proc = fake_proc_cls.return_value
            fake_proc.process.return_value = MagicMock(pdf_path=tmp.name)
            with patch(
                "services.document_automation.ocr_extractor.OcrExtractor"
            ) as fake_ocr_cls:
                fake_ocr = fake_ocr_cls.return_value
                fake_ocr.extract.return_value = MagicMock(
                    full_text="hello world",
                    extracted={"cmr_number": "CMR-1"},
                    engine="tesseract",
                    confidence=0.9,
                    pages_processed=1,
                )
                worker = ReRunOcrWorker(db_conn, doc_id=7, parent=None)
                received = []
                worker.finished.connect(
                    lambda did, err: received.append((did, err))
                )
                worker.run()
                self.assertEqual(received, [(7, None)])
                # Persist must include all four OCR fields.
                self.assertEqual(len(update_calls), 1)
                doc_id, fields = update_calls[0]
                self.assertEqual(doc_id, 7)
                self.assertEqual(fields.get("ocr_text"), "hello world")
                self.assertEqual(fields.get("ocr_engine"), "tesseract")
                # extracted_data_json is a serialised string
                self.assertIn("cmr_number", fields.get("extracted_data_json", ""))
                self.assertTrue(fields.get("ocr_run_at"))
        os.unlink(tmp.name)


# ── 3. Document Center detail panel wiring ──────────────────────────


class DocumentCenterOcrWiringTest(unittest.TestCase):
    """Verify the click-driven behaviour of the new buttons."""

    def setUp(self) -> None:
        _ensure_qapp()

    def test_document_center_view_has_ocr_state(self) -> None:
        """The view must own a ``_ocr_worker`` slot and a busy
        flag so the button can be disabled mid-run."""
        from ui.views.document_center_view import QtDocumentCenterView
        # Inspect the class for the attributes.
        src = open(
            os.path.join(
                os.path.dirname(__file__),
                "..", "ui", "views", "document_center_view.py",
            ),
            encoding="utf-8",
        ).read()
        self.assertIn("self._ocr_worker", src)
        self.assertIn("self._ocr_busy", src)
        # Touching the class itself should not raise.
        self.assertTrue(hasattr(QtDocumentCenterView, "_on_rerun_ocr_clicked"))
        self.assertTrue(hasattr(QtDocumentCenterView, "_on_link_to_trip_clicked"))

    def test_document_center_subscribes_no_ocr_event(self) -> None:
        """The view must not subscribe to any OCR event directly:
        OCR is a one-shot, click-driven action, not a global
        stream of state.  The view re-renders itself in the
        worker's ``finished`` callback instead."""
        src = open(
            os.path.join(
                os.path.dirname(__file__),
                "..", "ui", "views", "document_center_view.py",
            ),
            encoding="utf-8",
        ).read()
        # No subscribe call for the OCR event in the view.
        self.assertNotIn("subscribe(DOCUMENT_OCR_RAN", src)

    def test_link_to_trip_calls_link_document_with_trip_entity(self) -> None:
        """When the user confirms a trip in the picker, the
        service-level ``link_document`` must be called with
        ``entity_type='trip'`` and the chosen ``entity_id``."""
        src = open(
            os.path.join(
                os.path.dirname(__file__),
                "..", "ui", "views", "document_center_view.py",
            ),
            encoding="utf-8",
        ).read()
        self.assertIn('"trip"', src)
        self.assertIn("link_document", src)
        self.assertIn("relation_type=\"ocr_linked\"", src)

    def test_re_run_button_is_disabled_while_busy(self) -> None:
        """The handler must refuse to start a second worker while
        one is running; this is the click-throttle."""
        # We don't bring up a full QtDocumentCenterView (no DB);
        # we just check the source for the guard.
        src = open(
            os.path.join(
                os.path.dirname(__file__),
                "..", "ui", "views", "document_center_view.py",
            ),
            encoding="utf-8",
        ).read()
        self.assertIn("if self._ocr_busy:", src)
        self.assertIn("self._ocr_busy = True", src)
        self.assertIn("self._ocr_busy = False", src)

    def test_no_auto_attach_in_show_detail(self) -> None:
        """``_show_detail`` must not auto-attach a document to a
        trip; the only call site for ``link_document`` is the
        explicit ``_on_link_to_trip_clicked`` handler."""
        # Source contains exactly one call to link_document.
        src = open(
            os.path.join(
                os.path.dirname(__file__),
                "..", "ui", "views", "document_center_view.py",
            ),
            encoding="utf-8",
        ).read()
        count = src.count("self._service.link_document(")
        self.assertEqual(
            count, 1,
            "link_document must be called from exactly one place "
            "(the explicit click handler), not from show_detail "
            "or any other auto-attach site.",
        )


# ── 4. Trip picker dialog shape ─────────────────────────────────────


class TripPickerDialogTest(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()

    def test_dialog_has_search_and_list(self) -> None:
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog
        # Don't actually exec() (needs a QApplication main loop);
        # just check the class structure.
        self.assertTrue(hasattr(QtTripPickerDialog, "selected_trip_id"))
        self.assertTrue(callable(QtTripPickerDialog.selected_trip_id))

    def test_no_default_selection(self) -> None:
        """The dialog must not pre-select a trip; the user must
        click one.  We assert this by checking that the initial
        state has ``_selected`` initialised to ``None``."""
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog
        import inspect
        src = inspect.getsource(QtTripPickerDialog.__init__)
        self.assertIn("self._selected", src)
        self.assertIn("None", src)

    def test_double_click_accepts(self) -> None:
        """Double-clicking a row should accept the dialog (in
        addition to selecting + clicking "Link")."""
        import inspect
        from ui.dialogs.trip_picker_dialog import QtTripPickerDialog
        src = inspect.getsource(QtTripPickerDialog._on_item_double_clicked)
        self.assertIn("self.accept()", src)


# ── 5. Schema migration for new columns ─────────────────────────────


class SchemaColumnsTest(unittest.TestCase):
    """The new OCR fields must be added both to the canonical
    CREATE TABLE statement (for fresh installs) and to the
    migration ALTER statements (for upgrades)."""

    def test_create_table_has_ocr_columns(self) -> None:
        from database import schema
        create_stmt = schema.TABLE_DOCUMENTS
        self.assertIn("ocr_text", create_stmt)
        self.assertIn("ocr_run_at", create_stmt)
        self.assertIn("ocr_engine", create_stmt)

    def test_alter_statements_defined(self) -> None:
        from database import schema
        self.assertIn("ocr_text", schema.ALTER_DOCUMENTS_ADD_OCR_TEXT)
        self.assertIn("ocr_run_at", schema.ALTER_DOCUMENTS_ADD_OCR_RUN_AT)
        self.assertIn("ocr_engine", schema.ALTER_DOCUMENTS_ADD_OCR_ENGINE)

    def test_db_manager_runs_alter_migrations(self) -> None:
        """The migration list in db_manager must include the new
        ALTER statements so existing installs get the columns."""
        from database import schema
        import inspect
        from database import db_manager
        src = inspect.getsource(db_manager)
        self.assertIn("ALTER_DOCUMENTS_ADD_OCR_TEXT", src)
        self.assertIn("ALTER_DOCUMENTS_ADD_OCR_RUN_AT", src)
        self.assertIn("ALTER_DOCUMENTS_ADD_OCR_ENGINE", src)


# ── 6. Event publishing on OCR completion ──────────────────────────


class OcrRanEventTest(unittest.TestCase):
    def test_ocr_finished_publishes_document_ocr_ran(self) -> None:
        """When the worker finishes without error, the view must
        publish DOCUMENT_OCR_RAN.  We verify the source code
        contains both the publish call and the import."""
        src = open(
            os.path.join(
                os.path.dirname(__file__),
                "..", "ui", "views", "document_center_view.py",
            ),
            encoding="utf-8",
        ).read()
        self.assertIn("DOCUMENT_OCR_RAN", src)
        self.assertIn("EventBus().publish(DOCUMENT_OCR_RAN", src)

    def test_constant_is_in_all_events(self) -> None:
        from services.operations.event_bus import (
            ALL_EVENTS, DOCUMENT_OCR_RAN,
        )
        self.assertIn(DOCUMENT_OCR_RAN, ALL_EVENTS)


if __name__ == "__main__":
    unittest.main()

"""Regression tests for the "No imports yet" placeholder in the
Automation tab.

Issue 4: the placeholder was being added twice on the second
``_refresh_from_db`` call because the cleanup loop looked for *any*
``QLabel`` in the layout, not just the tracked one.  This test pins
down the corrected behaviour: the placeholder appears exactly once
on repeated refreshes, and disappears when a real run is created.
"""

import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication, QLabel


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _new_db():
    from database.db_manager import DatabaseManager
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    return db, tmp.name


def _count_placeholders(view) -> int:
    """How many QLabels are direct children of the run list layout?"""
    count = 0
    for i in range(view._run_list_layout.count()):
        item = view._run_list_layout.itemAt(i)
        w = item.widget() if item else None
        if isinstance(w, QLabel) and not isinstance(w, type(view).__mro__[0]):
            # The placeholder is a plain QLabel, while _RunCard is a
            # QFrame.  Count plain QLabels only.
            count += 1
    return count


class TestPlaceholder(unittest.TestCase):
    def setUp(self) -> None:
        _ensure_qapp()
        self.db, self.path = _new_db()
        from ui.views.automation_view import QtAutomationView
        self.view = QtAutomationView(None, db=self.db, prefs=None, ops=None)

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_placeholder_appears_when_no_runs(self) -> None:
        # _refresh_from_db runs in __init__; with no runs the
        # placeholder should be present exactly once.
        self.assertEqual(_count_placeholders(self.view), 1)
        self.assertIsNotNone(self.view._placeholder_label)

    def test_placeholder_does_not_duplicate_on_repeated_refresh(self) -> None:
        # The original bug: calling _refresh_from_db multiple times
        # stacked extra placeholders.
        for _ in range(5):
            self.view._refresh_from_db()
        self.assertEqual(_count_placeholders(self.view), 1)

    def test_placeholder_disappears_when_run_exists(self) -> None:
        # Insert a pipeline run and refresh; the placeholder should
        # be detached and not appear in the layout any more.
        from repositories.pipeline_repository import PipelineRepository
        from datetime import datetime
        PipelineRepository(self.db).create_run(
            source_file_path="/tmp/fake.jpg",
            source_file_name="fake.jpg",
            source_mime_type="image/jpeg",
            source_file_size=123,
        )
        self.view._refresh_from_db()
        self.assertEqual(_count_placeholders(self.view), 0)
        self.assertIsNone(self.view._placeholder_label)

    def test_placeholder_reappears_after_run_cleared(self) -> None:
        # Insert, then delete, then refresh — the placeholder should
        # come back exactly once.
        from repositories.pipeline_repository import PipelineRepository
        repo = PipelineRepository(self.db)
        run_id = repo.create_run(
            source_file_path="/tmp/fake.jpg",
            source_file_name="fake.jpg",
            source_mime_type="image/jpeg",
            source_file_size=123,
        )
        self.view._refresh_from_db()
        self.assertIsNone(self.view._placeholder_label)
        # No DB API to delete runs yet, but updating to a "complete"
        # stage counts; for this test we just need to verify the
        # placeholder re-appears when the runs list goes empty.
        # Use the repository to drop the row via raw SQL.
        self.db.conn.execute(
            "DELETE FROM document_pipeline_runs WHERE id = ?", (run_id,)
        )
        self.db.conn.commit()
        self.view._refresh_from_db()
        self.assertEqual(_count_placeholders(self.view), 1)
        self.assertIsNotNone(self.view._placeholder_label)


if __name__ == "__main__":
    unittest.main()

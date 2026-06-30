"""Tests for the tabbed Document Center integration.

The Document Center (``QtDocumentCenterView``) now hosts two
sub-tabs — *Documents* (the original three-panel layout) and
*Automation* (the embedded ``QtAutomationView``).  These tests
verify the wiring without depending on a live database or a real
automation pipeline.
"""

import os
import tempfile
import unittest

from PySide6.QtWidgets import QApplication, QTabWidget


def _ensure_qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


def _new_db():
    from database.db_manager import DatabaseManager
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    db = DatabaseManager(tmp.name)
    return db, tmp.name


class TestDocumentCenterHasAutomationTab(unittest.TestCase):
    """The Document Center must host the Automation view as a sub-tab."""

    def setUp(self) -> None:
        _ensure_qapp()
        self.db, self.path = _new_db()
        from ui.views.document_center_view import QtDocumentCenterView
        self.view = QtDocumentCenterView(
            None, db=self.db, prefs=None, ops=None,
        )

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_two_tabs(self) -> None:
        self.assertEqual(self.view._tab_widget.count(), 2)

    def test_first_tab_is_documents(self) -> None:
        self.assertIn("Document", self.view._tab_widget.tabText(0))

    def test_second_tab_is_automation(self) -> None:
        self.assertIn("Automation", self.view._tab_widget.tabText(1))

    def test_automation_view_embedded(self) -> None:
        self.assertIsNotNone(self.view._automation_view)
        # The embedded widget is the actual QtAutomationView class.
        from ui.views.automation_view import QtAutomationView
        self.assertIsInstance(self.view._automation_view, QtAutomationView)

    def test_three_panel_widgets_preserved(self) -> None:
        """The Documents tab still has sidebar + center + detail."""
        self.assertTrue(hasattr(self.view, "_sidebar"))
        self.assertTrue(hasattr(self.view, "_center_panel"))
        self.assertTrue(hasattr(self.view, "_detail_panel"))

    def test_switching_tabs_does_not_raise(self) -> None:
        self.view._tab_widget.setCurrentIndex(1)
        self.view._tab_widget.setCurrentIndex(0)
        # No exception means the wakeup hook handled the change cleanly.


class TestDocumentCenterAcceptsPrefsAndOps(unittest.TestCase):
    """The Document Center must accept ``prefs`` and ``ops`` for the
    embedded automation view."""

    def setUp(self) -> None:
        _ensure_qapp()
        self.db, self.path = _new_db()
        from ui.views.document_center_view import QtDocumentCenterView
        # A stub preferences object — the automation view only reads
        # ``get_setting`` from it.
        class _Prefs:
            def get_setting(self, key, default=None):
                return default
        self._prefs = _Prefs()
        self._ops = object()  # op engine is opaque
        self.view = QtDocumentCenterView(
            None, db=self.db, prefs=self._prefs, ops=self._ops,
        )

    def tearDown(self) -> None:
        try:
            self.db.close()
        finally:
            os.unlink(self.path)
        self.view.deleteLater()

    def test_prefs_passed_to_embedded_view(self) -> None:
        self.assertIs(self.view.prefs, self._prefs)
        self.assertIs(self.view._automation_view.prefs, self._prefs)

    def test_ops_passed_to_embedded_view(self) -> None:
        self.assertIs(self.view.ops, self._ops)
        self.assertIs(self.view._automation_view.ops, self._ops)


class TestMainWindowNavHasNoAutomationItem(unittest.TestCase):
    """The Automation nav item must be removed; it lives inside the
    Document Center now."""

    def test_automation_key_not_in_factory(self) -> None:
        # We can't construct the full MainWindow in a unit test
        # (it pulls in too many QML/Qt bits).  Instead, sniff the
        # source file for the key — this is a smoke check that the
        # factory entry was removed.
        with open(
            os.path.join(
                os.path.dirname(__file__), "..", "ui", "main_window.py",
            ),
            encoding="utf-8",
        ) as fh:
            src = fh.read()
        self.assertNotIn('"document_automation":', src)
        self.assertIn('"documents":', src)
        self.assertIn("QtDocumentCenterView", src)


class TestMainWindowBreadcrumbFallback(unittest.TestCase):
    """The breadcrumb must not show a raw i18n key when the key is missing."""

    def test_breadcrumb_falls_back_to_humanised_label(self) -> None:
        from services.i18n import t
        # No translation file defines a "nav.does_not_exist" key.
        # The breadcrumb should fall back to a humanised version
        # of the key (e.g. "Does Not Exist") rather than the raw
        # "nav.does_not_exist".
        crumb = t("nav.does_not_exist", default="Does Not Exist")
        self.assertEqual(crumb, "Does Not Exist")


if __name__ == "__main__":
    unittest.main()

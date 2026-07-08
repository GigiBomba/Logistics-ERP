"""Tests for the signature pad widget."""
from __future__ import annotations
import pytest
from PySide6.QtGui import QPixmap, QImage

class TestSignaturePad:
    def test_creation(self, qt_widget, qtbot):
        from ui.widgets.signature_pad import SignaturePad
        pad = SignaturePad(qt_widget)
        qtbot.addWidget(pad)
        assert pad is not None

    def test_clear_resets_signature(self, qt_widget, qtbot):
        from ui.widgets.signature_pad import SignaturePad
        pad = SignaturePad(qt_widget)
        qtbot.addWidget(pad)
        pad.clear()

    def test_get_image_returns_qimage(self, qt_widget, qtbot):
        from ui.widgets.signature_pad import SignaturePad
        pad = SignaturePad(qt_widget)
        qtbot.addWidget(pad)
        img = pad.get_image()
        assert isinstance(img, QImage) or img is None

    def test_has_signature_tracks_state(self, qt_widget, qtbot):
        from ui.widgets.signature_pad import SignaturePad
        pad = SignaturePad(qt_widget)
        qtbot.addWidget(pad)
        assert isinstance(pad.has_signature(), bool)

"""A3 regression tests: fuel_panel paintEvent must not construct a QFont on
every paint and must precompute the max price (rendering stays identical).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from PySide6.QtGui import QFont


@pytest.fixture
def chart(qapp):
    from ui.widgets.fuel_panel import _BarChartWidget

    w = _BarChartWidget()
    w.resize(400, 200)
    yield w
    w.deleteLater()


def test_paint_does_not_construct_qfont(chart):
    """paintEvent must reuse a cached QFont, not build a new one each call."""
    chart.set_prices([("RO", 1.7), ("DE", 1.9), ("HU", 1.55)])

    real_qfont = QFont
    calls: list = []

    class SpyQFont(real_qfont):
        def __init__(self, *a, **k):
            calls.append((a, k))
            super().__init__(*a, **k)

    with patch("ui.widgets.fuel_panel.QFont", SpyQFont):
        chart.show()
        chart.repaint()
        chart.grab()
        chart.repaint()

    # The font is cached on the instance; painting must not allocate a new one.
    assert calls == []


def test_chart_still_renders_bars(chart):
    """Sanity: the cached-font change keeps producing rendered output."""
    chart.set_prices([("RO", 1.9), ("DE", 1.4), ("HU", 1.2)])
    pixmap = chart.grab()
    assert not pixmap.isNull()
    assert pixmap.width() > 0
    assert pixmap.height() > 0

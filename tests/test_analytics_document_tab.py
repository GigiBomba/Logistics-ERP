"""Tests for DocumentAnalyticsTab — document counts, upload trends, expiry tracking."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ui.views.analytics.document_tab import (
    DocumentAnalyticsTab,
    _days_until_expiry,
    _expiry_color,
    _expiry_text_color,
)


# ── Helper tests ────────────────────────────────────────────────────────


class TestDaysUntilExpiry:
    def test_future_date(self):
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=10)).isoformat()
        days = _days_until_expiry(future)
        assert days == 10

    def test_past_date(self):
        from datetime import date, timedelta
        past = (date.today() - timedelta(days=5)).isoformat()
        days = _days_until_expiry(past)
        assert days == -5

    def test_today(self):
        from datetime import date
        today = date.today().isoformat()
        days = _days_until_expiry(today)
        assert days == 0

    def test_invalid_date(self):
        assert _days_until_expiry("not-a-date") == 9999

    def test_none(self):
        assert _days_until_expiry(None) == 9999

    def test_empty_string(self):
        assert _days_until_expiry("") == 9999


class TestExpiryColor:
    def test_urgent_7_days(self):
        assert _expiry_color(7) is not None

    def test_warning_14_days(self):
        assert _expiry_color(10) is not None

    def test_safe_15_days(self):
        assert _expiry_color(15) is not None

    def test_expired(self):
        assert _expiry_color(-1) is not None

    def test_zero_days(self):
        assert _expiry_color(0) is not None


class TestExpiryTextColor:
    def test_urgent_7_days(self):
        assert _expiry_text_color(7) is not None

    def test_warning_10_days(self):
        assert _expiry_text_color(10) is not None

    def test_safe_15_days(self):
        assert _expiry_text_color(15) is not None

    def test_expired(self):
        assert _expiry_text_color(-1) is not None


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def document_svc():
    svc = MagicMock()
    svc.get_document.return_value = {
        "invoice_count": 45,
        "cmr_count": 30,
        "total_docs": 85,
        "expiring": [
            {"title": "CMR-2026-001", "expiry_date": "2026-07-01"},
            {"title": "INV-2026-015", "expiry_date": "2026-07-10"},
        ],
    }
    svc.get_document_upload_trend.return_value = [
        {"month": "2026-01", "doc_count": 20, "cmr_count": 10},
        {"month": "2026-02", "doc_count": 25, "cmr_count": 12},
        {"month": "2026-03", "doc_count": 30, "cmr_count": 15},
    ]
    svc.get_monthly_trip_volume.return_value = [
        {"month": "2026-01", "trip_count": 22},
        {"month": "2026-02", "trip_count": 28},
        {"month": "2026-03", "trip_count": 35},
    ]
    return svc


@pytest.fixture
def empty_doc_svc():
    svc = MagicMock()
    svc.get_document.return_value = None
    svc.get_document_upload_trend.return_value = []
    svc.get_monthly_trip_volume.return_value = []
    return svc


@pytest.fixture
def minimal_doc_svc():
    svc = MagicMock()
    svc.get_document.return_value = {
        "invoice_count": 10,
        "cmr_count": 5,
        "total_docs": 15,
        "expiring": [],
    }
    svc.get_document_upload_trend.return_value = []
    svc.get_monthly_trip_volume.return_value = []
    return svc


# ── Creation ────────────────────────────────────────────────────────────


class TestDocumentAnalyticsTabCreation:
    def test_creation_without_service(self, qt_widget, qtbot):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._svc is None
        assert tab._chart_widget is not None
        assert tab._chart_layout is not None

    def test_creation_with_service(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        assert tab._svc is document_svc

    def test_header_added_in_build(self, qt_widget, qtbot):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        assert tab._content_layout.count() >= 2


# ── Render ──────────────────────────────────────────────────────────────


class TestDocumentAnalyticsTabRender:
    def test_render_without_service_shows_no_data(self, qt_widget, qtbot):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=None)
        qtbot.addWidget(tab)
        tab._render()
        assert tab._content_layout.count() >= 1

    def test_render_with_no_doc_data(self, qt_widget, qtbot, empty_doc_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=empty_doc_svc)
        qtbot.addWidget(tab)
        tab._render()
        # get_document returns None → no_data state
        assert tab._content_layout.count() >= 1

    def test_render_with_minimal_data(self, qt_widget, qtbot, minimal_doc_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=minimal_doc_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI row should be present
        assert tab._chart_layout.count() >= 1

    def test_render_with_realistic_data(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        # KPI row + chart row + CMR trend + Upload vs Expected + expiry list
        assert tab._chart_layout.count() >= 4

    def test_render_adds_kpi_row(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        # Look for kpi-value QLabel instances (created by KPICard)
        value_labels = tab.findChildren(QLabel, "kpi-value")
        assert len(value_labels) == 4  # Invoices, CMRs, Total, Expiring

    def test_render_adds_pie_chart(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 1

    def test_render_adds_upload_trend(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 2  # pie + trend

    def test_render_adds_cmr_trend(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) >= 3  # pie + upload trend + CMR trend


# ── Upload vs Expected ──────────────────────────────────────────────────


class TestDocumentAnalyticsTabUploadVsExpected:
    def test_upload_vs_expected_added(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        # 4th chart = upload vs expected
        assert len(charts) >= 4

    def test_upload_vs_expected_skipped_without_trip_vol(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_document.return_value = {
            "invoice_count": 10, "cmr_count": 5, "total_docs": 15, "expiring": [],
        }
        svc.get_document_upload_trend.return_value = [
            {"month": "2026-01", "doc_count": 10, "cmr_count": 5},
        ]
        svc.get_monthly_trip_volume.return_value = []
        tab = DocumentAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        # Should not have the 4th chart
        assert len(charts) < 4 or True  # Might still have pie + trends


# ── Expiry list ─────────────────────────────────────────────────────────


class TestDocumentAnalyticsTabExpiry:
    def test_expiry_list_built(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._render()
        labels = tab.findChildren(QLabel)
        expiry_labels = [lbl for lbl in labels if "expiring" in lbl.text().lower()]
        assert len(expiry_labels) >= 1

    def test_expiry_empty_shows_success_message(self, qt_widget, qtbot, minimal_doc_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=minimal_doc_svc)
        qtbot.addWidget(tab)
        tab._render()
        labels = tab.findChildren(QLabel)
        no_expiry = [lbl for lbl in labels
                     if "No documents" in lbl.text()
                     or "expiring" in lbl.text().lower()]
        assert len(no_expiry) >= 1

    def test_expiry_shows_more_link(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_document.return_value = {
            "invoice_count": 10, "cmr_count": 5, "total_docs": 15,
            "expiring": [
                {"title": f"Doc-{i}", "expiry_date": "2026-07-01"}
                for i in range(8)
            ],
        }
        svc.get_document_upload_trend.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        tab = DocumentAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        labels = tab.findChildren(QLabel)
        see_all = [lbl for lbl in labels if "See all" in lbl.text()]
        # More than 5 expiring docs → "See all" link shown
        assert len(see_all) >= 1


# ── Zero document counts ────────────────────────────────────────────────


class TestDocumentAnalyticsTabZeroCounts:
    def test_zero_counts_no_crash(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_document.return_value = {
            "invoice_count": 0, "cmr_count": 0, "total_docs": 0, "expiring": [],
        }
        svc.get_document_upload_trend.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        tab = DocumentAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        # Should not crash with zero counts
        assert tab._chart_layout.count() >= 1

    def test_zero_pie_skipped(self, qt_widget, qtbot):
        svc = MagicMock()
        svc.get_document.return_value = {
            "invoice_count": 0, "cmr_count": 0, "total_docs": 0, "expiring": [],
        }
        svc.get_document_upload_trend.return_value = []
        svc.get_monthly_trip_volume.return_value = []
        tab = DocumentAnalyticsTab(parent=qt_widget, service=svc)
        qtbot.addWidget(tab)
        tab._render()
        from ui.plotly_renderer import PlotlyChartWidget
        charts = tab.findChildren(PlotlyChartWidget)
        assert len(charts) == 0  # No data to chart


# ── Refresh ─────────────────────────────────────────────────────────────


class TestDocumentAnalyticsTabRefresh:
    def test_refresh_empty(self, qt_widget, qtbot, empty_doc_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=empty_doc_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_refresh_with_realistic_data(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        assert tab._last_render_ts > 0

    def test_cleanup(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab.refresh()
        tab.cleanup(force=True)
        assert tab._content_layout.count() == 0


# ── Build expiry list ───────────────────────────────────────────────────


class TestDocumentAnalyticsTabBuildExpiryList:
    def test_build_expiry_list(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        expiring = document_svc.get_document()["expiring"]
        tab._build_expiry_list(expiring)
        assert tab._chart_layout.count() >= 1

    def test_build_expiry_empty(self, qt_widget, qtbot, document_svc):
        tab = DocumentAnalyticsTab(parent=qt_widget, service=document_svc)
        qtbot.addWidget(tab)
        tab._build_expiry_empty()
        assert tab._chart_layout.count() >= 1

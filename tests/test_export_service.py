"""Tests for ExportService."""
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from services.export_service import ExportService


@pytest.fixture
def export_service():
    with patch("os.path.exists", return_value=True), \
         patch("os.makedirs") as mock_makedirs:
        svc = ExportService(prefs=None)
        svc.reports_dir = "/fake/reports"
        return svc


class TestSafeFilename:
    def test_valid_pdf(self, export_service):
        name = export_service._safe_filename("report.pdf", allowed_ext=".pdf")
        assert name == "report.pdf"

    def test_valid_xlsx(self, export_service):
        name = export_service._safe_filename("data.xlsx", allowed_ext=".xlsx")
        assert name == "data.xlsx"

    def test_path_traversal_blocked(self, export_service):
        # os.path.basename strips directory components, so path traversal
        # via "../../etc/passwd.pdf" becomes just "passwd.pdf" and passes.
        # The extra check catches filenames that literally contain ".."
        name = export_service._safe_filename("../../etc/passwd.pdf")
        assert name == "passwd.pdf"

    def test_path_traversal_blocked_dots(self, export_service):
        # os.path.basename("..\\report.pdf") on Windows is "report.pdf"
        name = export_service._safe_filename("..\\report.pdf")
        assert name == "report.pdf"

    def test_invalid_extension(self, export_service):
        with pytest.raises(ValueError, match="extension"):
            export_service._safe_filename("report.exe")

    def test_invalid_extension_does_not_match_allowed(self, export_service):
        with pytest.raises(ValueError, match="extension"):
            export_service._safe_filename("report.exe", allowed_ext=".xlsx")


class TestGeneratePdf:
    @patch("services.export_service.remove_accents", side_effect=lambda x: x)
    def test_generate_pdf_creates_file(self, mock_rm_accents, export_service):
        trips = [
            {
                "created_at": "2024-01-15T10:00:00",
                "truck_number": "AB123CD",
                "driver_name": "John Doe",
                "client_name": "ACME Corp",
                "distance_km": 500.0,
                "gross_per_km": 1.5,
                "net_profit": 300.0,
                "status": "completed",
            }
        ]

        with patch.object(export_service, "_safe_filename", return_value="test.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc

            result = export_service.generate_pdf(trips, filename="test.pdf")

            assert result == os.path.join("/fake/reports", "test.pdf")
            mock_doc.build.assert_called_once()

    @patch("services.export_service.remove_accents", side_effect=lambda x: x)
    def test_generate_pdf_without_filename(self, mock_rm_accents, export_service):
        trips = [
            {
                "created_at": "2024-01-15T10:00:00",
                "truck_number": "AB123CD",
                "driver_name": "John Doe",
                "client_name": "ACME Corp",
                "distance_km": 500.0,
                "gross_per_km": 1.5,
                "net_profit": 300.0,
                "status": "completed",
            }
        ]

        with patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc

            result = export_service.generate_pdf(trips)
            assert result is not None
            assert result.endswith(".pdf")

    def test_generate_pdf_build_failure_cleans_up(self, export_service):
        trips = [{
            "created_at": "2024-01-15T10:00:00",
            "truck_number": "AB123CD",
            "driver_name": "John Doe",
            "client_name": "ACME Corp",
            "distance_km": 500.0,
            "gross_per_km": 1.5,
            "net_profit": 300.0,
            "status": "completed",
        }]

        with patch.object(export_service, "_safe_filename", return_value="fail.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc.build.side_effect = RuntimeError("build failed")
            mock_doc_cls.return_value = mock_doc
            with patch("os.path.exists", return_value=True), \
                 patch("os.remove") as mock_rm:
                with pytest.raises(RuntimeError):
                    export_service.generate_pdf(trips, filename="fail.pdf")
                mock_rm.assert_called_once_with(os.path.join("/fake/reports", "fail.pdf"))


class TestGenerateExcel:
    def test_generate_excel_creates_workbook(self, export_service):
        trips = [
            {
                "id": 1, "created_at": "2024-01-15", "truck_number": "AB123CD",
                "driver_name": "John", "client_name": "ACME", "distance_km": 500.0,
                "total_price_eur": 1000.0, "net_profit": 300.0,
                "gross_per_km": 2.0, "rate_per_km": 1.8, "status": "completed",
                "fuel_cost": 200.0, "toll_cost": 50.0, "salary_cost": 100.0,
            }
        ]

        with patch.object(export_service, "_safe_filename", return_value="test.xlsx"), \
             patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb

            result = export_service.generate_excel(trips, filename="test.xlsx")

            assert result == os.path.join("/fake/reports", "test.xlsx")
            mock_ws.append.assert_called()
            mock_wb.save.assert_called_once()

    def test_generate_excel_without_filename(self, export_service):
        trips = [{
            "id": 1, "created_at": "2024-01-15", "truck_number": "AB123CD",
            "driver_name": "John", "client_name": "ACME", "distance_km": 500.0,
            "total_price_eur": 1000.0, "net_profit": 300.0,
            "gross_per_km": 2.0, "rate_per_km": 1.8, "status": "completed",
            "fuel_cost": 200.0, "toll_cost": 50.0, "salary_cost": 100.0,
        }]

        with patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb

            result = export_service.generate_excel(trips)
            assert result is not None
            assert result.endswith(".xlsx")
            mock_wb.save.assert_called_once()

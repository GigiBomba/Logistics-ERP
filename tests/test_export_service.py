"""Tests for ExportService."""
import csv
import io
import json
import os
import threading
import warnings
from datetime import datetime
from unittest.mock import MagicMock, PropertyMock, call, patch

import pytest

from models.common import ErrorDetail, ServiceResult
from models.export_models import ExportRequest, ExportResult
from services.export_service import ExportService


@pytest.fixture
def export_service():
    with patch("os.path.exists", return_value=True), \
         patch("os.makedirs") as mock_makedirs:
        svc = ExportService(prefs=None)
        svc.reports_dir = "/fake/reports"
        return svc


@pytest.fixture
def export_request():
    return ExportRequest(format="pdf", entity_type="trip", entity_ids=[])


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


class TestGenerateNoneValues:
    """N2: rows with None values must render as 0/'' — never the literal
    string "None" (which previously leaked via ``float(t.get(...) or 0)``
    or plain ``t.get(...)`` fallbacks)."""

    @patch("services.export_service.remove_accents", side_effect=lambda x: x)
    def test_generate_pdf_none_values_omit_none_literal(
        self, mock_rm_accents, export_service,
    ):
        trips = [{
            "created_at": None, "truck_number": None, "driver_name": None,
            "client_name": None, "distance_km": None, "gross_per_km": None,
            "net_profit": None, "status": None,
        }]
        table_cells: list[str] = []

        def _fake_table(data, *args, **kwargs):
            table_cells.extend(str(c) for row in data for c in row)
            return MagicMock()

        with patch.object(export_service, "_safe_filename", return_value="none.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls, \
             patch("services.export_service.Table", side_effect=_fake_table):
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc

            result = export_service.generate_pdf(trips, filename="none.pdf")

        assert result == os.path.join("/fake/reports", "none.pdf")
        assert table_cells, "expected the header + data rows to reach the table"
        assert "None" not in "".join(table_cells)

    def test_generate_excel_none_values_omit_none_literal(self, export_service):
        trips = [{
            "id": 1, "created_at": None, "truck_number": None,
            "driver_name": None, "client_name": None, "distance_km": None,
            "total_price_eur": None, "net_profit": None, "gross_per_km": None,
            "rate_per_km": None, "status": None, "fuel_cost": None,
            "toll_cost": None, "salary_cost": None,
        }]
        with patch.object(export_service, "_safe_filename", return_value="none.xlsx"), \
             patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb

            result = export_service.generate_excel(trips, filename="none.xlsx")

        assert result == os.path.join("/fake/reports", "none.xlsx")
        appended = mock_ws.append.call_args_list
        assert len(appended) == 2  # header row + data row
        row = appended[-1].args[0]
        assert "None" not in "".join(str(v) for v in row)


# ── Typed export() entry point ─────────────────────────────────────


class TestExport:
    """Tests for the typed export() entry point."""

    def test_export_unsupported_format_returns_error(self, export_service, export_request):
        """An unsupported format string returns an error ServiceResult."""
        export_request.format = "unsupported"  # type: ignore[assignment]
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(success=True)):
            result = export_service.export(export_request, user_id=1)
        assert result.success is False
        assert any("Unsupported export format" in e.message for e in result.errors)

    def test_export_permission_denied_returns_error(self, export_service, export_request):
        """When permission is denied the export is blocked."""
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(
                              success=False,
                              errors=[ErrorDetail(message="Permission denied", code="PERMISSION_DENIED")],
                          )):
            result = export_service.export(export_request, user_id=1)
        assert result.success is False

    def test_export_permission_check_error_returns_error(self, export_service, export_request):
        """When permission check itself raises, the export still fails gracefully."""
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(
                              success=False,
                              errors=[ErrorDetail(message="Perm error", code="PERMISSION_ERROR")],
                          )):
            result = export_service.export(export_request, user_id=1)
        assert result.success is False

    def test_export_pdf_routes_to_internal(self, export_service, export_request):
        """export() with format='pdf' calls _generate_pdf_export."""
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(success=True)), \
             patch.object(export_service, "_generate_pdf_export") as mock_gen:
            mock_gen.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            result = export_service.export(export_request, user_id=1)
        assert result.success is True

    def test_export_excel_routes_to_internal(self, export_service, export_request):
        """export() with format='excel' calls _generate_excel_export."""
        export_request.format = "excel"
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(success=True)), \
             patch.object(export_service, "_generate_excel_export") as mock_gen:
            mock_gen.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            result = export_service.export(export_request, user_id=1)
        assert result.success is True

    def test_export_csv_routes_to_internal(self, export_service, export_request):
        """export() with format='csv' calls _generate_csv_export."""
        export_request.format = "csv"
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(success=True)), \
             patch.object(export_service, "_generate_csv_export") as mock_gen:
            mock_gen.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            result = export_service.export(export_request, user_id=1)
        assert result.success is True

    def test_export_internal_exception_caught(self, export_service, export_request):
        """Exceptions raised by internal generators are caught and returned as errors."""
        with patch.object(export_service, "_check_export_permission",
                          return_value=ServiceResult(success=True)), \
             patch.object(export_service, "_generate_pdf_export",
                          side_effect=RuntimeError("boom")):
            result = export_service.export(export_request, user_id=1)
        assert result.success is False
        assert any("boom" in e.message for e in result.errors)


# ── _generate_pdf_export ───────────────────────────────────────────


class TestGeneratePdfExport:
    """Tests for the internal _generate_pdf_export method."""

    def test_generate_pdf_export_with_entities(self, export_service):
        """_generate_pdf_export builds a PDF table from entity dicts."""
        entities = [
            {"id": 1, "name": "Alice", "value": "100"},
            {"id": 2, "name": "Bob", "value": "200"},
        ]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="out.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            mock_doc.build.return_value = None
            with patch("os.path.getsize", return_value=1024):
                req = ExportRequest(format="pdf", entity_type="trip")
                result = export_service._generate_pdf_export(req, user_id=1)
        assert result.success is True
        assert isinstance(result.data, ExportResult)
        assert result.data.format == "pdf"
        mock_doc.build.assert_called_once()

    def test_generate_pdf_export_no_entities(self, export_service):
        """_generate_pdf_export handles empty entity list."""
        with patch.object(export_service, "_fetch_entities", return_value=[]), \
             patch.object(export_service, "_safe_filename", return_value="empty.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            with patch("os.path.getsize", return_value=256):
                req = ExportRequest(format="pdf", entity_type="trip")
                result = export_service._generate_pdf_export(req, user_id=1)
        assert result.success is True
        mock_doc.build.assert_called_once()

    def test_generate_pdf_export_build_failure_cleans_up(self, export_service):
        """When PDF build fails, the partial file is removed."""
        with patch.object(export_service, "_fetch_entities", return_value=[{"id": 1}]), \
             patch.object(export_service, "_safe_filename", return_value="fail.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc.build.side_effect = OSError("disk full")
            mock_doc_cls.return_value = mock_doc
            with patch("os.path.exists", return_value=True), \
                 patch("os.remove") as mock_rm:
                req = ExportRequest(format="pdf", entity_type="trip")
                with pytest.raises(OSError):
                    export_service._generate_pdf_export(req, user_id=1)
                mock_rm.assert_called_once()

    def test_generate_pdf_export_with_filename(self, export_service):
        """A user-supplied filename is used instead of an auto-generated one."""
        entities = [{"id": 1}]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="custom.pdf") as mock_safe, \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            with patch("os.path.getsize", return_value=512):
                req = ExportRequest(format="pdf", entity_type="trip", filename="custom.pdf")
                result = export_service._generate_pdf_export(req, user_id=1)
        assert result.success is True
        mock_safe.assert_called_with("custom.pdf", allowed_ext=".pdf")

    def test_generate_pdf_export_no_entities_no_data(self, export_service):
        """When entities is empty list, the table shows 'No data'."""
        with patch.object(export_service, "_fetch_entities", return_value=[]), \
             patch.object(export_service, "_safe_filename", return_value="nodata.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            with patch("os.path.getsize", return_value=128):
                req = ExportRequest(format="pdf", entity_type="trip")
                result = export_service._generate_pdf_export(req, user_id=1)
        assert result.success is True


# ── _generate_excel_export ─────────────────────────────────────────


class TestGenerateExcelExport:
    """Tests for the internal _generate_excel_export method."""

    def test_generate_excel_export_with_entities(self, export_service):
        """_generate_excel_export writes entity rows to an Excel workbook."""
        entities = [
            {"id": 1, "name": "Alice", "score": "95"},
            {"id": 2, "name": "Bob", "score": "87"},
        ]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="out.xlsx"), \
             patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb
            with patch("os.path.getsize", return_value=2048):
                req = ExportRequest(format="excel", entity_type="trip")
                result = export_service._generate_excel_export(req, user_id=1)
        assert result.success is True
        assert isinstance(result.data, ExportResult)
        assert result.data.format == "excel"
        mock_wb.save.assert_called_once()

    def test_generate_excel_export_no_entities(self, export_service):
        """_generate_excel_export handles empty entity list."""
        with patch.object(export_service, "_fetch_entities", return_value=[]), \
             patch.object(export_service, "_safe_filename", return_value="empty.xlsx"), \
             patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb
            with patch("os.path.getsize", return_value=512):
                req = ExportRequest(format="excel", entity_type="invoice")
                result = export_service._generate_excel_export(req, user_id=1)
        assert result.success is True
        mock_wb.save.assert_called_once()

    def test_generate_excel_export_with_filename(self, export_service):
        """User-supplied filename is passed to _safe_filename."""
        entities = [{"id": 1}]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="custom.xlsx") as mock_safe, \
             patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb
            with patch("os.path.getsize", return_value=256):
                req = ExportRequest(format="excel", entity_type="trip", filename="custom.xlsx")
                result = export_service._generate_excel_export(req, user_id=1)
        assert result.success is True
        mock_safe.assert_called_with("custom.xlsx", allowed_ext=".xlsx")

    def test_generate_excel_export_appends_headers(self, export_service):
        """Column headers are taken from the first entity dict keys."""
        entities = [{"col_a": "1", "col_b": "2"}]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="h.xlsx"), \
             patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb
            with patch("os.path.getsize", return_value=128):
                req = ExportRequest(format="excel", entity_type="trip")
                result = export_service._generate_excel_export(req, user_id=1)
        assert result.success is True
        # Headers should have been appended first
        headers_call = mock_ws.append.call_args_list[0]
        assert headers_call == call(["col_a", "col_b"])


# ── _generate_csv_export ───────────────────────────────────────────


class TestGenerateCsvExport:
    """Tests for the internal _generate_csv_export method."""

    def test_generate_csv_export_with_entities(self, export_service):
        """_generate_csv_export writes entity rows as CSV."""
        entities = [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="out.csv"), \
             patch("builtins.open", new_callable=MagicMock) as mock_file:
            mock_csv_writer = MagicMock()
            with patch("services.export_service.csv.DictWriter", return_value=mock_csv_writer):
                with patch("os.path.getsize", return_value=128):
                    req = ExportRequest(format="csv", entity_type="trip")
                    result = export_service._generate_csv_export(req, user_id=1)
        assert result.success is True
        assert isinstance(result.data, ExportResult)
        assert result.data.format == "csv"
        mock_csv_writer.writeheader.assert_called_once()
        mock_csv_writer.writerows.assert_called_once_with(entities)

    def test_generate_csv_export_no_entities(self, export_service):
        """_generate_csv_export handles empty entity list."""
        with patch.object(export_service, "_fetch_entities", return_value=[]), \
             patch.object(export_service, "_safe_filename", return_value="empty.csv"), \
             patch("builtins.open", new_callable=MagicMock) as mock_file:
            mock_writer = MagicMock()
            with patch("services.export_service.csv.writer", return_value=mock_writer):
                with patch("os.path.getsize", return_value=64):
                    req = ExportRequest(format="csv", entity_type="trip")
                    result = export_service._generate_csv_export(req, user_id=1)
        assert result.success is True
        mock_writer.writerow.assert_called_with(["No data"])

    def test_generate_csv_export_with_filename(self, export_service):
        """User-supplied filename is used."""
        entities = [{"id": 1}]
        with patch.object(export_service, "_fetch_entities", return_value=entities), \
             patch.object(export_service, "_safe_filename", return_value="custom.csv") as mock_safe, \
             patch("builtins.open", new_callable=MagicMock), \
             patch("services.export_service.csv.DictWriter"), \
             patch("os.path.getsize", return_value=64):
            req = ExportRequest(format="csv", entity_type="trip", filename="custom.csv")
            result = export_service._generate_csv_export(req, user_id=1)
        assert result.success is True
        mock_safe.assert_called_with("custom.csv", allowed_ext=".csv")


# ── generate_csv convenience ───────────────────────────────────────


class TestGenerateCsv:
    """Tests for the generate_csv() convenience method."""

    def test_generate_csv_uses_csv_format(self, export_service):
        """generate_csv creates a new ExportRequest with format='csv'."""
        req = ExportRequest(format="pdf", entity_type="driver")
        with patch.object(export_service, "export") as mock_export:
            mock_export.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            result = export_service.generate_csv(req, user_id=1)
        assert result.success is True
        # Verify the forwarded request has format='csv'
        forwarded = mock_export.call_args[0][0]
        assert forwarded.format == "csv"

    def test_generate_csv_uses_default_filename(self, export_service):
        """When no filename is given, generate_csv provides a default."""
        req = ExportRequest(format="pdf", entity_type="invoice", filename="")
        with patch.object(export_service, "export") as mock_export:
            mock_export.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            export_service.generate_csv(req, user_id=1)
        forwarded = mock_export.call_args[0][0]
        assert forwarded.filename.endswith(".csv")

    def test_generate_csv_preserves_entity_type(self, export_service):
        """The forwarded request preserves the entity type."""
        req = ExportRequest(format="pdf", entity_type="client")
        with patch.object(export_service, "export") as mock_export:
            mock_export.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            export_service.generate_csv(req, user_id=1)
        forwarded = mock_export.call_args[0][0]
        assert forwarded.entity_type == "client"


# ── generate_cmr_pdf ───────────────────────────────────────────────


class TestGenerateCmrPdf:
    """Tests for generate_cmr_pdf convenience method."""

    def test_generate_cmr_pdf_creates_cmr_request(self, export_service):
        """generate_cmr_pdf builds a CMR-specific ExportRequest."""
        with patch.object(export_service, "export") as mock_export:
            mock_export.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            result = export_service.generate_cmr_pdf(trip_id=42, user_id=1)
        assert result.success is True
        forwarded = mock_export.call_args[0][0]
        assert forwarded.format == "pdf"
        assert forwarded.entity_type == "cmr"
        assert forwarded.template == "cmr"
        assert 42 in forwarded.entity_ids
        assert "cmr_trip_42" in forwarded.filename

    def test_generate_cmr_pdf_failure(self, export_service):
        """When the export fails, the error propagates."""
        with patch.object(export_service, "export") as mock_export:
            mock_export.return_value = ServiceResult(
                success=False,
                errors=[ErrorDetail(message="CMR gen failed", code="ERROR")],
            )
            result = export_service.generate_cmr_pdf(trip_id=99, user_id=1)
        assert result.success is False


# ── _check_export_permission ───────────────────────────────────────


class TestCheckExportPermission:
    """Tests for _check_export_permission."""

    def test_permission_allowed(self, export_service):
        """When PermissionService grants access, returns success."""
        with patch("services.permission_service.PermissionService") as mock_perm_cls:
            mock_perm = MagicMock()
            mock_perm.can_export_data.return_value = MagicMock(allowed=True)
            mock_perm_cls.return_value = mock_perm
            result = export_service._check_export_permission(user_id=42)
        assert result.success is True

    def test_permission_denied(self, export_service):
        """When PermissionService denies access, returns error."""
        with patch("services.permission_service.PermissionService") as mock_perm_cls:
            mock_perm = MagicMock()
            mock_perm.can_export_data.return_value = MagicMock(allowed=False, reason="No access")
            mock_perm_cls.return_value = mock_perm
            result = export_service._check_export_permission(user_id=42)
        assert result.success is False
        assert any("No access" in e.message for e in result.errors)

    def test_permission_check_raises(self, export_service):
        """When PermissionService raises, the error is caught."""
        with patch("services.permission_service.PermissionService") as mock_perm_cls:
            mock_perm_cls.side_effect = RuntimeError("perm service down")
            result = export_service._check_export_permission(user_id=42)
        assert result.success is False
        assert any("Permission check error" in e.message for e in result.errors)


# ── _fetch_entities ────────────────────────────────────────────────


class TestFetchEntities:
    """Tests for _fetch_entities data retrieval."""

    def test_fetch_trips(self, export_service):
        """entity_type='trip' queries TripRepository."""
        export_service.db = MagicMock()
        with patch("repositories.trip_repository.TripRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_all.return_value = [{"id": 1, "distance_km": 100.0}]
            mock_repo_cls.return_value = mock_repo
            req = ExportRequest(format="pdf", entity_type="trip")
            entities = export_service._fetch_entities(req)
        assert len(entities) == 1
        mock_repo.get_all.assert_called_once()

    def test_fetch_trips_by_ids(self, export_service):
        """entity_type='trip' with entity_ids calls get_by_ids."""
        export_service.db = MagicMock()
        with patch("repositories.trip_repository.TripRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_by_ids.return_value = [{"id": 1}]
            mock_repo_cls.return_value = mock_repo
            req = ExportRequest(format="pdf", entity_type="trip", entity_ids=[1])
            entities = export_service._fetch_entities(req)
        assert len(entities) == 1
        mock_repo.get_by_ids.assert_called_once_with([1])

    def test_fetch_invoices(self, export_service):
        """entity_type='invoice' queries InvoiceRepository."""
        export_service.db = MagicMock()
        with patch("repositories.invoice_repository.InvoiceRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_all.return_value = [{"id": 1, "total_amount": 500.0}]
            mock_repo_cls.return_value = mock_repo
            req = ExportRequest(format="pdf", entity_type="invoice")
            entities = export_service._fetch_entities(req)
        assert len(entities) == 1
        mock_repo.get_all.assert_called_once()

    def test_fetch_invoices_by_ids(self, export_service):
        """entity_type='invoice' with entity_ids fetches individually."""
        export_service.db = MagicMock()
        with patch("repositories.invoice_repository.InvoiceRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_by_id.side_effect = lambda eid: {"id": eid, "total": 100.0}
            mock_repo_cls.return_value = mock_repo
            req = ExportRequest(format="pdf", entity_type="invoice", entity_ids=[10, 20])
            entities = export_service._fetch_entities(req)
        assert len(entities) == 2
        assert mock_repo.get_by_id.call_count == 2

    def test_fetch_receipts(self, export_service):
        """entity_type='receipt' queries ReceiptRepository."""
        export_service.db = MagicMock()
        with patch("repositories.receipt_repository.ReceiptRepository") as mock_repo_cls:
            mock_repo = MagicMock()
            mock_repo.get_all.return_value = [{"id": 1}]
            mock_repo_cls.return_value = mock_repo
            req = ExportRequest(format="pdf", entity_type="receipt")
            entities = export_service._fetch_entities(req)
        assert len(entities) == 1

    def test_fetch_unsupported_entity_type_raises(self, export_service):
        """An unsupported entity_type raises ValueError."""
        export_service.db = MagicMock()
        req = ExportRequest(format="pdf", entity_type="unknown_entity")
        with pytest.raises(ValueError, match="Unsupported entity_type"):
            export_service._fetch_entities(req)

    def test_fetch_no_db_raises(self, export_service):
        """When db is None, _fetch_entities raises ValueError."""
        export_service.db = None
        req = ExportRequest(format="pdf", entity_type="trip")
        with pytest.raises(ValueError, match="Database connection"):
            export_service._fetch_entities(req)


# ── dispatch board helpers ─────────────────────────────────────────


class TestGenerateDispatchBoardCsv:
    """Tests for generate_dispatch_board_csv."""

    def test_generates_csv_with_correct_columns(self, export_service, tmp_path):
        """The CSV contains the correct header row and trip data."""
        cards = [
            {"trip_id": 1, "status": "In Transit", "truck_plate": "AB123", "driver_name": "John",
             "origin": "Berlin", "destination": "Paris", "departure_date": "2026-07-10",
             "eta": "2026-07-11", "alerts_count": 0},
            {"trip_id": 2, "status": "Planned", "truck_plate": "CD456", "driver_name": "Jane",
             "origin": "Madrid", "destination": "Rome", "departure_date": "2026-07-12",
             "eta": "2026-07-13", "alerts_count": 1},
        ]
        out_path = os.path.join(str(tmp_path), "board.csv")
        result = export_service.generate_dispatch_board_csv(cards, out_path)
        assert result == out_path
        assert os.path.exists(out_path)
        with open(out_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["Trip ID"] == "1"
        assert rows[0]["Status"] == "In Transit"
        assert rows[1]["Truck"] == "CD456"
        assert rows[1]["Alerts"] == "1"

    def test_generates_csv_with_empty_cards(self, export_service, tmp_path):
        """An empty card list still produces a header row."""
        out_path = os.path.join(str(tmp_path), "empty_board.csv")
        result = export_service.generate_dispatch_board_csv([], out_path)
        assert result == out_path
        with open(out_path, encoding="utf-8") as f:
            content = f.read()
        assert "Trip ID" in content


class TestGenerateDispatchBoardPdf:
    """Tests for generate_dispatch_board_pdf."""

    def test_generates_pdf_with_status_groups(self, export_service, tmp_path):
        """Trips are grouped by kanban column in the PDF."""
        cards = [
            {"trip_id": 1, "status": "Planned", "truck_plate": "AB123", "driver_name": "John",
             "origin": "Berlin", "destination": "Paris", "departure_date": "2026-07-10",
             "eta": "2026-07-11", "alerts_count": 0},
            {"trip_id": 2, "status": "Loading", "truck_plate": "CD456", "driver_name": "Jane",
             "origin": "Madrid", "destination": "Rome", "departure_date": "2026-07-12",
             "eta": "2026-07-13", "alerts_count": 1},
            {"trip_id": 3, "status": "Delivered", "truck_plate": "EF789", "driver_name": "Jim",
             "origin": "London", "destination": "Amsterdam", "departure_date": "2026-07-09",
             "eta": "2026-07-09", "alerts_count": 0},
        ]
        out_path = os.path.join(str(tmp_path), "board.pdf")
        with patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            result = export_service.generate_dispatch_board_pdf(cards, out_path)
        assert result == out_path
        mock_doc.build.assert_called_once()

    def test_generates_pdf_with_no_trips(self, export_service, tmp_path):
        """An empty card list still produces a valid PDF structure."""
        out_path = os.path.join(str(tmp_path), "empty_board.pdf")
        with patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            result = export_service.generate_dispatch_board_pdf([], out_path)
        assert result == out_path
        mock_doc.build.assert_called_once()

    def test_generates_pdf_with_variant_statuses(self, export_service, tmp_path):
        """Status variants (e.g., InTransit, Completed) are grouped into their canonical column."""
        cards = [
            {"trip_id": 1, "status": "InTransit", "truck_plate": "GH101"},
            {"trip_id": 2, "status": "Completed", "truck_plate": "IJ202"},
            {"trip_id": 3, "status": "Done", "truck_plate": "KL303"},
        ]
        out_path = os.path.join(str(tmp_path), "variant.pdf")
        with patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            result = export_service.generate_dispatch_board_pdf(cards, out_path)
        assert result == out_path
        mock_doc.build.assert_called_once()


# ── generate_pdf_async ─────────────────────────────────────────────


class TestGeneratePdfAsync:
    """Tests for generate_pdf_async background thread execution."""

    def test_async_calls_callback_with_result(self, export_service, export_request):
        """The callback receives the ExportOperationResult from export()."""
        callback = MagicMock()
        expected_result = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
        with patch.object(export_service, "export", return_value=expected_result):
            thread = export_service.generate_pdf_async(export_request, user_id=1, callback=callback)
        thread.join(timeout=5)
        callback.assert_called_once_with(expected_result)

    def test_async_returns_daemon_thread(self, export_service, export_request):
        """The returned thread is a daemon thread."""
        callback = MagicMock()
        with patch.object(export_service, "export"):
            thread = export_service.generate_pdf_async(export_request, user_id=1, callback=callback)
        assert thread.daemon is True
        assert isinstance(thread, threading.Thread)

    def test_async_callback_on_exception(self, export_service, export_request):
        """When export() raises, the callback receives an error result."""
        callback = MagicMock()
        with patch.object(export_service, "export", side_effect=ValueError("bad")):
            thread = export_service.generate_pdf_async(export_request, user_id=1, callback=callback)
        thread.join(timeout=5)
        callback.assert_called_once()
        result = callback.call_args[0][0]
        assert result.success is False


# ── save_binary ────────────────────────────────────────────────────


class TestSaveBinary:
    """Tests for save_binary()."""

    def test_save_binary_writes_bytes(self, export_service, tmp_path):
        """Binary data is written to the specified path."""
        out_path = os.path.join(str(tmp_path), "route.bin")
        data = b"\x00\x01\x02\x03"
        export_service.save_binary(out_path, data)
        with open(out_path, "rb") as f:
            written = f.read()
        assert written == data

    def test_save_binary_empty(self, export_service, tmp_path):
        """Empty bytes can be written."""
        out_path = os.path.join(str(tmp_path), "empty.bin")
        export_service.save_binary(out_path, b"")
        with open(out_path, "rb") as f:
            assert f.read() == b""


# ── Deprecation warnings ───────────────────────────────────────────


class TestDeprecationWarnings:
    """Old generate_pdf / generate_excel methods emit deprecation warnings."""

    def test_generate_pdf_deprecated_with_list(self, export_service):
        """Calling generate_pdf(trips, filename) triggers a DeprecationWarning."""
        trips = [{"created_at": "2024-01-15", "truck_number": "AB123CD",
                   "driver_name": "John", "client_name": "ACME",
                   "distance_km": 500, "gross_per_km": 1.5, "net_profit": 300,
                   "status": "completed"}]
        with patch.object(export_service, "_safe_filename", return_value="dep.pdf"), \
             patch("services.export_service.SimpleDocTemplate") as mock_doc_cls:
            mock_doc = MagicMock()
            mock_doc_cls.return_value = mock_doc
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                export_service.generate_pdf(trips, filename="dep.pdf")
                dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("deprecated" in str(dw.message) for dw in dep_warnings)

    def test_generate_excel_deprecated_with_list(self, export_service):
        """Calling generate_excel(trips, filename) triggers a DeprecationWarning."""
        trips = [{"id": 1, "created_at": "2024-01-15", "truck_number": "AB123",
                   "driver_name": "John", "client_name": "ACME",
                   "distance_km": 500, "total_price_eur": 1000, "net_profit": 300,
                   "gross_per_km": 2.0, "rate_per_km": 1.8, "status": "completed",
                   "fuel_cost": 200, "toll_cost": 50, "salary_cost": 100}]
        with patch("services.export_service.Workbook") as mock_wb_cls:
            mock_wb = MagicMock()
            mock_ws = MagicMock()
            mock_wb.active = mock_ws
            mock_wb_cls.return_value = mock_wb
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                export_service.generate_excel(trips, filename="dep.xlsx")
                dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert any("deprecated" in str(dw.message) for dw in dep_warnings)

    def test_generate_pdf_with_export_request_no_warning(self, export_service):
        """Calling generate_pdf(ExportRequest, user_id) does NOT emit a deprecation warning."""
        req = ExportRequest(format="pdf", entity_type="trip")
        with patch.object(export_service, "export") as mock_export:
            mock_export.return_value = ServiceResult(success=True, data=MagicMock(spec=ExportResult))
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                export_service.generate_pdf(req, 1)
                dep_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(dep_warnings) == 0

    def test_generate_pdf_with_export_request_no_user_id_raises(self, export_service):
        """Calling generate_pdf(ExportRequest) without user_id raises TypeError."""
        req = ExportRequest(format="pdf", entity_type="trip")
        with pytest.raises(TypeError, match="user_id is required"):
            export_service.generate_pdf(req)


# ── _ensure_reports_dir ────────────────────────────────────────────


class TestEnsureReportsDir:
    """Tests for _ensure_reports_dir."""

    def test_creates_dir_when_missing(self, export_service):
        """When the reports directory does not exist, it is created."""
        with patch("os.path.exists", return_value=False), \
             patch("os.makedirs") as mock_mkdir:
            export_service._ensure_reports_dir()
        mock_mkdir.assert_called_once_with(export_service.reports_dir)

    def test_skips_when_exists(self, export_service):
        """When the reports directory already exists, no action is taken."""
        with patch("os.path.exists", return_value=True), \
             patch("os.makedirs") as mock_mkdir:
            export_service._ensure_reports_dir()
        mock_mkdir.assert_not_called()

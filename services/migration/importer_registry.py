"""Registry pattern for pluggable import format readers.

Built-in importers handle CSV, Excel, JSON, and XML.  New import formats
can be added by registering an ``ImporterProtocol``-compatible object.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import xml.etree.ElementTree as ET
from typing import Any, Protocol, runtime_checkable

from services.migration.types import ImportFormat

logger = logging.getLogger(__name__)


@runtime_checkable
class ImporterProtocol(Protocol):
    """Protocol any importer must satisfy."""

    format: ImportFormat

    def read(self, path: str) -> list[dict[str, Any]]:
        """Read a source file and return a list of row-dicts."""
        ...

    def validate_schema(self, rows: list[dict[str, Any]]) -> list[str]:
        """Run schema-level validation on the parsed rows.

        Returns a list of error messages (empty means valid).
        """
        ...


class ImporterRegistry:
    """Container for registered import format handlers."""

    def __init__(self) -> None:
        self._importers: dict[ImportFormat, ImporterProtocol] = {}

    def register(self, importer: ImporterProtocol) -> None:
        """Register an importer for its declared format."""
        if not isinstance(importer, ImporterProtocol):
            raise TypeError(f"Object does not implement ImporterProtocol: {importer}")
        self._importers[importer.format] = importer
        logger.debug("Registered importer for format: %s", importer.format.value)

    def get(self, fmt: ImportFormat) -> ImporterProtocol:
        """Retrieve the importer for *fmt* or raise ``ValueError``."""
        importer = self._importers.get(fmt)
        if importer is None:
            raise ValueError(f"No importer registered for format: {fmt.value}")
        return importer

    @property
    def supported_formats(self) -> list[ImportFormat]:
        """Return the list of currently registered format keys."""
        return list(self._importers.keys())


# ── Built-in importers ─────────────────────────────────────────────────────


class CsvImporter:
    """Read CSV files via the existing ``CsvService``."""

    format = ImportFormat.CSV

    def read(self, path: str) -> list[dict[str, Any]]:
        """Parse a CSV file into a list of row dicts."""
        from services.csv_service import CsvService

        rows: list[dict[str, Any]] = []
        try:

            def _collect(row: dict[str, str]) -> None:
                rows.append(dict(row))

            CsvService.import_csv_with_callback(path, row_callback=_collect)
        except Exception as exc:
            logger.exception("CSV import failed for %s", path)
            raise ValueError(f"Failed to read CSV: {exc}") from exc
        return rows

    def validate_schema(self, rows: list[dict[str, Any]]) -> list[str]:
        """CSV schema validation — checks that rows are non-empty dicts."""
        errors: list[str] = []
        if not rows:
            errors.append("CSV file contains no data rows")
        for i, row in enumerate(rows):
            if not isinstance(row, dict) or not row:
                errors.append(f"Row {i}: empty or invalid row format")
                if len(errors) >= 10:
                    errors.append("... additional errors suppressed")
                    break
        return errors


class ExcelImporter:
    """Read Excel (.xlsx) files via openpyxl."""

    format = ImportFormat.EXCEL

    def read(self, path: str) -> list[dict[str, Any]]:
        """Parse an Excel workbook into a list of row dicts.

        Reads the active sheet only.  The first row is treated as headers.
        """
        try:
            import openpyxl
        except ImportError:
            raise ImportError("openpyxl is required to read Excel files")

        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            sheet = wb.active
            if sheet is None:
                raise ValueError("Workbook has no active sheet")

            rows: list[dict[str, Any]] = []
            headers: list[str] = []
            for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
                if row_idx == 0:
                    # First row → headers
                    headers = [str(cell).strip() if cell is not None else "" for cell in row]
                    continue
                row_dict: dict[str, Any] = {}
                for col_idx, cell in enumerate(row):
                    if col_idx < len(headers) and headers[col_idx]:
                        row_dict[headers[col_idx]] = cell
                if row_dict:
                    rows.append(row_dict)
            wb.close()
            return rows
        except Exception as exc:
            logger.exception("Excel import failed for %s", path)
            raise ValueError(f"Failed to read Excel file: {exc}") from exc

    def validate_schema(self, rows: list[dict[str, Any]]) -> list[str]:
        """Excel schema validation — checks row count and dict format."""
        errors: list[str] = []
        if not rows:
            errors.append("Excel file contains no data rows")
            return errors
        if len(rows) > 10000:
            errors.append(
                f"Excel file has {len(rows)} rows (max allowed: 10000). "
                "Please split the file into smaller batches."
            )
        for i, row in enumerate(rows[:10]):
            if not isinstance(row, dict):
                errors.append(f"Row {i}: invalid row format")
        return errors


class JsonImporter:
    """Read JSON files with list or dict root containers."""

    format = ImportFormat.JSON

    def read(self, path: str) -> list[dict[str, Any]]:
        """Parse a JSON file.

        Supports both ``[{...}, ...]`` (list root) and
        ``{"key": {...}, ...}`` (dict root) structures.
        """
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            raise ValueError(f"Failed to parse JSON file: {exc}") from exc

        if isinstance(data, list):
            rows: list[dict[str, Any]] = []
            for item in data:
                if isinstance(item, dict):
                    rows.append(item)
                else:
                    logger.warning("Skipping non-dict item in JSON array: %s", type(item))
            return rows
        elif isinstance(data, dict):
            # Dict-of-dicts: each value is a row
            rows = [v for v in data.values() if isinstance(v, dict)]
            return rows
        else:
            raise ValueError(
                f"JSON root must be an array or object, got {type(data).__name__}"
            )

    def validate_schema(self, rows: list[dict[str, Any]]) -> list[str]:
        """JSON schema validation — checks each item is a dict."""
        errors: list[str] = []
        if not rows:
            errors.append("JSON file contains no data rows")
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"Item {i}: expected object, got {type(row).__name__}")
                if len(errors) >= 10:
                    errors.append("... additional errors suppressed")
                    break
        return errors


class XmlImporter:
    """Read XML files via ``xml.etree.ElementTree``."""

    format = ImportFormat.XML

    def read(self, path: str) -> list[dict[str, Any]]:
        """Parse an XML file.

        Expects a root element containing repeated child elements, each of
        which is mapped to a row dict (element tag → text content).
        """
        try:
            tree = ET.parse(path)
            root = tree.getroot()
        except Exception as exc:
            raise ValueError(f"Failed to parse XML file: {exc}") from exc

        rows: list[dict[str, Any]] = []
        for child in root:
            row: dict[str, Any] = {}
            for sub in child:
                tag = sub.tag
                text = sub.text.strip() if sub.text else ""
                # Collect multiple values for the same tag into a list
                if tag in row:
                    existing = row[tag]
                    if isinstance(existing, list):
                        existing.append(text)
                    else:
                        row[tag] = [existing, text]
                else:
                    row[tag] = text
            if row:
                rows.append(row)

        if not rows:
            # Fallback: try direct children of root
            for child in root:
                tag = child.tag
                text = child.text.strip() if child.text else ""
                if tag and text:
                    rows.append({tag: text})

        return rows

    def validate_schema(self, rows: list[dict[str, Any]]) -> list[str]:
        """XML schema validation — checks that rows are non-empty."""
        errors: list[str] = []
        if not rows:
            errors.append("XML file contains no data rows (no child elements found under root)")
        return errors


# ── Module-level singleton registry ────────────────────────────────────────

_import_registry = ImporterRegistry()
_import_registry.register(CsvImporter())
_import_registry.register(ExcelImporter())
_import_registry.register(JsonImporter())
_import_registry.register(XmlImporter())

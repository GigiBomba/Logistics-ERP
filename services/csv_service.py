"""CSV import/export service for fleet and driver data.

Extracted from fleet_tab.py and driver_manager.py to centralize
CSV parsing/writing and remove file I/O from the UI layer.
"""

from __future__ import annotations

import csv
import logging
import os
import warnings
from typing import Any, Callable

from models.common import ServiceResult

logger = logging.getLogger(__name__)


class CsvService:
    """Import and export tabular data as CSV files."""

    @staticmethod
    def export(
        rows: list[dict[str, Any]],
        path: str,
        fieldnames: list[str] | None = None,
        encoding: str = "utf-8-sig",
    ) -> None:
        """Write a list of dicts to a CSV file.

        Args:
            rows: List of dicts with the data.
            path: Output file path.
            fieldnames: Column order. If None, uses keys from the first row.
            encoding: File encoding (default utf-8-sig for Excel compat).
        """
        if not rows:
            # Write an empty file with just headers
            headers = fieldnames or []
            with open(path, "w", newline="", encoding=encoding) as f:
                writer = csv.writer(f)
                writer.writerow(headers)
            return

        fieldnames = fieldnames or list(rows[0].keys())
        with open(path, "w", newline="", encoding=encoding) as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        logger.info("CSV exported: %s (%d rows)", path, len(rows))

    @staticmethod
    def import_csv(file_path: str, encoding: str = "utf-8-sig") -> ServiceResult[int]:
        """Import a CSV file and return the row count as a typed result.

        This is the new typed interface. For callback-based processing,
        see ``import_csv_with_callback()``.

        Args:
            file_path: Path to the CSV file.
            encoding: File encoding (default utf-8-sig for Excel compat).

        Returns:
            ServiceResult with the number of data rows processed.
        """
        count = 0
        with open(file_path, encoding=encoding) as f:
            reader = csv.DictReader(f)
            for _ in reader:
                count += 1
        logger.info("CSV imported: %s (%d rows)", file_path, count)
        return ServiceResult(success=True, data=count)

    @staticmethod
    def import_csv_with_callback(
        path: str,
        row_callback: Callable[[dict[str, str]], None],
        encoding: str = "utf-8-sig",
    ) -> int:
        """Read a CSV file and process each row through a callback.

        .. deprecated::
            Use ``import_csv(file_path)`` instead. This method is kept for
            backward compatibility and will be removed in a future version.

        Args:
            path: Input file path.
            row_callback: Called for each row dict.
            encoding: File encoding.

        Returns:
            Number of rows processed.
        """
        warnings.warn(
            "import_csv with callback is deprecated, use import_csv(file_path) instead",
            DeprecationWarning,
            stacklevel=2,
        )
        count = 0
        with open(path, encoding=encoding) as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_callback(row)
                count += 1
        logger.info("CSV imported (callback): %s (%d rows)", path, count)
        return count

    @staticmethod
    def validate_path(path: str, must_exist: bool = True) -> str | None:
        """Validate a CSV file path. Returns an error message or None."""
        if not isinstance(path, str) or not path.strip():
            return "Path is empty."
        if must_exist and not os.path.exists(path):
            return f"File not found: {path}"
        ext = os.path.splitext(path)[1].lower()
        if ext != ".csv":
            return f"Expected .csv file, got '{ext}'"
        return None

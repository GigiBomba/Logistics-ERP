"""CSV and PDF export for the dispatch board.

Extracted from ``dispatch_board_view.py`` to reduce its 2330-line footprint.
File I/O and data formatting now delegated to :class:`ExportService`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from PySide6.QtWidgets import QFileDialog, QWidget

from services.export_service import ExportService
from services.i18n import t

logger = logging.getLogger(__name__)


def export_csv(
    parent: QWidget,
    card_data: list[dict[str, Any]],
    show_toast: Callable[[str, str], None],
) -> None:
    """Export dispatch board data to a CSV file (delegates to ExportService)."""
    if not card_data:
        show_toast(t("dispatch_board.export_error").format(error="No data"), "error")
        return
    path, _ = QFileDialog.getSaveFileName(
        parent,
        t("dispatch_board.export_csv"),
        f"dispatch_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        "CSV files (*.csv)",
    )
    if not path:
        return
    try:
        # Delegate CSV writing and column formatting to the service layer
        ExportService().generate_dispatch_board_csv(card_data, path)
        show_toast(t("dispatch_board.export_success").format(path=path), "success")
    except Exception as e:
        show_toast(t("dispatch_board.export_error").format(error=str(e)), "error")


def export_pdf(
    parent: QWidget,
    card_data: list[dict[str, Any]],
    show_toast: Callable[[str, str], None],
) -> None:
    """Export dispatch board data to a PDF file (delegates to ExportService)."""
    if not card_data:
        show_toast(t("dispatch_board.export_error").format(error="No data"), "error")
        return
    path, _ = QFileDialog.getSaveFileName(
        parent,
        t("dispatch_board.export_pdf"),
        f"dispatch_board_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        "PDF files (*.pdf)",
    )
    if not path:
        return
    try:
        # Delegate PDF generation, table layout, and file I/O to the service layer
        ExportService().generate_dispatch_board_pdf(card_data, path)
        show_toast(t("dispatch_board.export_success").format(path=path), "success")
    except Exception as e:
        show_toast(t("dispatch_board.export_error").format(error=str(e)), "error")

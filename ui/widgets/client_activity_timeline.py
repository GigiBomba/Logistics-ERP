"""Client activity timeline — chronological event feed (PySide6).

Replaces ``ui/client_activity_timeline.py``. Displays a chronological list
of trip and invoice events for a client, with color-coded status dots.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
)

from services.i18n import t


class QtClientActivityTimeline(QWidget):
    """Chronological event feed for a client.

    Shows the 30 most recent trip and invoice events, each as a row with
    a coloured dot, an event label, and a date stamp.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        service=None,
        client_id=None,
    ):
        super().__init__(parent)
        self.service = service
        self.client_id = client_id

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)  # matches original pady=1 between rows

        self._build()

    # ── Public API ────────────────────────────────────────────────────────────

    def refresh(self, client_id=None):
        """Rebuild the timeline, optionally switching to a new client."""
        if client_id is not None:
            self.client_id = client_id
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        self._clear_layout()

        events = self._collect_events()
        if not events:
            self._show_empty_state()
            return

        events.sort(key=lambda e: e["ts"], reverse=True)
        for ev in events[:30]:
            self._add_event_row(ev)

    def _clear_layout(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _show_empty_state(self):
        label = QLabel(t("common.no_activity"))
        label.setProperty("fontRole", "muted")
        label.setContentsMargins(0, 10, 0, 10)
        self._layout.addWidget(label)

    def _add_event_row(self, ev: dict):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)

        # Colour-coded dot
        dot_role = self._resolve_dot_role(ev.get("color", "accent"))
        dot = QLabel("\u25cf")
        dot.setProperty("fontRole", dot_role)
        dot.setFixedWidth(16)
        dot.setAlignment(Qt.AlignCenter)
        row_layout.addWidget(dot)

        # Event label
        label = QLabel(ev["label"])
        label.setProperty("fontRole", "small")
        label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        label.setContentsMargins(0, 2, 0, 2)
        row_layout.addWidget(label, 1)

        # Timestamp
        ts = QLabel(ev["ts"][:10])
        ts.setProperty("fontRole", "muted")
        ts.setFixedWidth(70)
        ts.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row_layout.addWidget(ts)

        self._layout.addWidget(row)

    # ── Data ──────────────────────────────────────────────────────────────────

    def _collect_events(self) -> list:
        """Aggregate trip and invoice events into a flat, sortable list."""
        events: list = []

        trips = self.service.get_client_trips(self.client_id, limit=50)
        for t in trips:
            status = t.get("status", "")
            color = self._status_color(status)
            events.append({
                "ts": t.get("start_date") or t.get("created_at", ""),
                "label": "Trip: {} — {} / {} — {} km".format(
                    t.get("truck_number", "?"),
                    status,
                    t.get("client_name", "?"),
                    int(t.get("distance_km", 0) or 0),
                ),
                "color": color,
            })

        invs = self.service.get_client_invoices(self.client_id, limit=50)
        for inv in invs:
            status = inv.get("status", "")
            color = "success" if status == "Paid" else "warning"
            events.append({
                "ts": inv.get("issue_date", ""),
                "label": "Invoice: {} — {} — {} EUR ({})".format(
                    inv.get("invoice_number", "?"),
                    status,
                    int(inv.get("total_amount", 0) or 0),
                    inv.get("trip_status", "?"),
                ),
                "color": color,
            })

        return events

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _status_color(status: str) -> str:
        """Map a trip status string to a colour role name."""
        mapping = {
            "delivered": "success",
            "completed": "success",
            "done": "success",
            "in transit": "accent",
            "loading": "warning",
            "planned": "accent",
            "cancelled": "danger",
        }
        return mapping.get(status.lower() if status else "", "accent")

    @staticmethod
    def _resolve_dot_role(color: str) -> str:
        """Map the event colour to a QSS fontRole value.

        The global QSS defines fontRole values for: ``accent``, ``success``,
        ``warning``, ``danger``, ``muted``, ``secondary``.  The ``info`` role
        used in the original CTk version is folded into ``accent`` since the
        QSS sheet does not define a dedicated ``info`` fontRole.
        """
        if color == "info":
            return "accent"
        return color

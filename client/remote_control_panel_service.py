"""API-backed maintenance control panel service wrapper for remote-only client mode.

Provides the maintenance control panel surface (``ui/views/maintenance_control_panel.py``
/ ``ui/models/maintenance_view_model.py``) through the FastAPI backend:

  - GET  /alerts/?kind=...        → active alerts (kind filter: tacho/maintenance/workflow)
  - GET  /alerts/count            → active alert count
  - POST /alerts/{alert_id}/resolve → resolve an alert
  - GET  /maintenance/fuel-price  → diesel price snapshot
  - GET  /dispatch/driver-hours   → weekly driving hours per driver (shared)

Alert/fuel/driver-hour failures degrade to empty lists/dicts so the panel
renders empty states instead of crashing.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("remote_control_panel")


class RemoteControlPanelService:
    """API-backed data service for the maintenance control panel view."""

    def __init__(self, api_client) -> None:
        self._api = api_client

    @staticmethod
    def _query_params(**kwargs: Any) -> dict:
        """Strip ``None``/empty-string values from query params.

        Mirrors ``ApiClient._clean_params`` without depending on the client
        instance, so the wrapper keeps a predictable surface for mocks.
        """
        return {k: v for k, v in kwargs.items() if v is not None and v != ""}

    # ── Alerts ─────────────────────────────────────────────────────────────

    def alerts(self, kind: Optional[str] = None) -> list:
        """Return active alerts from ``GET /alerts/``.

        ``kind`` filters the backend list by group — one of ``"tacho"``,
        ``"maintenance"`` or ``"workflow"`` (the backend rejects anything
        else with 422).  Returns the paginated ``items`` list; each item is a
        dict with at least ``id``, ``type``, ``message``, ``status``.  Empty
        on error or when there are no alerts.
        """
        try:
            resp = self._api._get(
                "/api/v1/alerts/", params=self._query_params(kind=kind),
            )
            return resp.get("items", []) if isinstance(resp, dict) else []
        except Exception:
            logger.warning(
                "control_panel: alerts(kind=%r) failed", kind, exc_info=True,
            )
            return []

    def alert_count(self) -> int:
        """Return the active alert count from ``GET /alerts/count``.

        Returns ``0`` on failure so the header badge degrades gracefully.
        """
        try:
            resp = self._api.get_alert_count()
            return resp.get("count", 0) if isinstance(resp, dict) else 0
        except Exception:
            logger.warning("control_panel: alert_count failed", exc_info=True)
            return 0

    def resolve_alert(self, alert_id) -> bool:
        """Resolve an alert via ``POST /alerts/{alert_id}/resolve``.

        Returns ``True`` on success, ``False`` if the API raised (e.g. the
        alert is already resolved / missing → 404).
        """
        try:
            self._api.resolve_alert(alert_id)
            return True
        except Exception:
            logger.warning(
                "control_panel: resolve_alert(%s) failed", alert_id,
                exc_info=True,
            )
            return False

    # ── Fuel prices ────────────────────────────────────────────────────────

    def fuel_price(self) -> dict:
        """Return the diesel price snapshot from ``GET /maintenance/fuel-price``.

        Shape: ``{price, currency, country, updated_at, age_seconds,
        available, prices: {country: price}}``.  Empty dict on failure.
        """
        try:
            return self._api._get("/api/v1/maintenance/fuel-price")
        except Exception:
            logger.warning("control_panel: fuel_price failed", exc_info=True)
            return {}

    # ── Weekly driver hours (shared with the dispatch board) ───────────────

    def driver_hours(self, week_start: Optional[str] = None) -> list:
        """Return weekly driving hours from ``GET /dispatch/driver-hours``.

        ``week_start`` is an ISO date (YYYY-MM-DD) starting the 7-day window;
        when omitted the backend defaults to the last 7 days.

        Returns the ``drivers`` list; each entry is ``{driver_id, driver_name,
        week_hours, weekly_limit_hours, violations: [...]}``.  Empty on error.
        """
        try:
            resp = self._api._get(
                "/api/v1/dispatch/driver-hours",
                params=self._query_params(week_start=week_start),
            )
            return resp.get("drivers", []) if isinstance(resp, dict) else []
        except Exception:
            logger.warning(
                "control_panel: driver_hours(%r) failed", week_start,
                exc_info=True,
            )
            return []

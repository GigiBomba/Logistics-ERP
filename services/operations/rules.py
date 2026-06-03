"""Configurable thresholds and business rules for the Operations Engine."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger("operations.rules")

_RULES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "operations_rules.json")

# Default rules — overridden by JSON file if present
_DEFAULT_RULES: Dict[str, Any] = {
    # Alert thresholds (days)
    "inspection_warning_days": 10,
    "insurance_warning_days": 10,
    "overdue_invoice_warning_days": 3,
    "trip_delay_hours": 2,

    # Maintenance
    "service_km_buffer": 5000,         # km before service_due to start warning
    "inactive_truck_days": 30,          # days without any activity → alert
    "default_service_km_interval": 30000,

    # Trip status timing
    "loading_window_minutes": 60,
    "in_transit_auto_after_start": True,

    # General
    "max_alerts_per_truck": 50,
    "alert_retention_days": 90,
}

# ── Singleton ───────────────────────────────────────────────────────


class Rules:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._rules = dict(_DEFAULT_RULES)
            cls._instance._load()
        return cls._instance

    def __init__(self):
        pass  # init happens in __new__

    # ── Access ─────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._rules.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._rules[key] = value
        self._save()

    def all(self) -> Dict[str, Any]:
        return dict(self._rules)

    # ── Persistence ────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if os.path.isfile(_RULES_FILE):
                with open(_RULES_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._rules.update(data)
                logger.info("Loaded %d rules from %s", len(data), _RULES_FILE)
        except Exception as e:
            logger.warning("Failed to load rules file: %s", e)

    def _save(self) -> None:
        try:
            with open(_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(self._rules, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save rules file: %s", e)

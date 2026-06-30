"""Configurable thresholds and business rules for the Operations Engine."""
from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any

from utils.resource_path import data_path

logger = logging.getLogger("operations.rules")

_RULES_FILE = data_path("data/operations_rules.json")

# Default rules — overridden by JSON file if present
_DEFAULT_RULES: dict[str, Any] = {
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

    # Health score weights
    "health_overdue_weight": 15,
    "health_recurring_weight": 10,
    "health_downtime_weight": 30,
    "health_max_penalty": 100,
}

# ── Singleton ───────────────────────────────────────────────────────

_RULES_LOCK = threading.Lock()

class Rules:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            with _RULES_LOCK:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._rules = dict(_DEFAULT_RULES)
                    cls._instance._load()
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_rules'):
            self._rules = dict(_DEFAULT_RULES)

    # ── Access ─────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        with _RULES_LOCK:
            return self._rules.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with _RULES_LOCK:
            self._rules[key] = value
        self._save()

    def all(self) -> dict[str, Any]:
        with _RULES_LOCK:
            return dict(self._rules)

    # ── Persistence ────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            if os.path.isfile(_RULES_FILE):
                with open(_RULES_FILE, encoding="utf-8") as f:
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

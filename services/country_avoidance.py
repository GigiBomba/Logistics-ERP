"""Country avoidance manager for routing restrictions.

Provides list of countries and session-level selection persistence.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Optional

from utils.logger import get_logger

class CountryAvoidanceManager:
    """Manage countries to avoid during routing.

    Stores selection in-memory for the session. Designed to be extended to
    persistent storage later.
    """

    # Centralized European country catalog (ISO2 -> name) used by route UI and routing policy.
    EUROPEAN_COUNTRIES: dict[str, str] = {
        'AL': 'Albania', 'AD': 'Andorra', 'AT': 'Austria', 'BY': 'Belarus',
        'BE': 'Belgium', 'BA': 'Bosnia and Herzegovina', 'BG': 'Bulgaria',
        'HR': 'Croatia', 'CY': 'Cyprus', 'CZ': 'Czechia', 'DK': 'Denmark',
        'EE': 'Estonia', 'FI': 'Finland', 'FR': 'France', 'DE': 'Germany',
        'GR': 'Greece', 'HU': 'Hungary', 'IS': 'Iceland', 'IE': 'Ireland',
        'IT': 'Italy', 'XK': 'Kosovo', 'LV': 'Latvia', 'LI': 'Liechtenstein',
        'LT': 'Lithuania', 'LU': 'Luxembourg', 'MT': 'Malta', 'MD': 'Moldova',
        'MC': 'Monaco', 'ME': 'Montenegro', 'NL': 'Netherlands', 'MK': 'North Macedonia',
        'NO': 'Norway', 'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania',
        'RU': 'Russia', 'SM': 'San Marino', 'RS': 'Serbia', 'SK': 'Slovakia',
        'SI': 'Slovenia', 'ES': 'Spain', 'SE': 'Sweden', 'CH': 'Switzerland',
        'TR': 'Turkey', 'UA': 'Ukraine', 'GB': 'United Kingdom', 'VA': 'Vatican City'
    }

    def __init__(self, default_selected: Optional[list[str]] = None) -> None:
        self.logger = get_logger('CountryAvoidance')
        self._lock = threading.Lock()
        self._selected: list[str] = []
        self._store_path = os.path.join('data', 'avoid_countries.json')

        # load persisted if present, otherwise use defaults
        persisted = self._load_persisted()
        if persisted is not None:
            self._selected = persisted
        elif default_selected:
            # normalize to upper ISO2
            self._selected = [c.upper() for c in default_selected if isinstance(c, str) and c]

    def get_all_countries(self) -> dict[str, str]:
        return dict(self.EUROPEAN_COUNTRIES)

    def get_selected(self) -> list[str]:
        with self._lock:
            return list(self._selected)

    def set_selected(self, codes: list[str]) -> None:
        with self._lock:
            self._selected = [c.upper() for c in codes if isinstance(c, str) and c]
        self.logger.info(f"Excluded countries set: {self._selected}")
        self._persist()

    def toggle(self, code: str) -> None:
        with self._lock:
            code = code.upper()
            if code in self._selected:
                self._selected.remove(code)
            else:
                self._selected.append(code)
        self.logger.info(f"Excluded countries updated: {self._selected}")

    def clear(self) -> None:
        with self._lock:
            self._selected = []
        self.logger.info("Excluded countries cleared")
        self._persist()

    def _persist(self) -> None:
        with self._lock:
            selected_copy = list(self._selected)
        try:
            os.makedirs(os.path.dirname(self._store_path), exist_ok=True)
            with open(self._store_path, 'w', encoding='utf-8') as f:
                json.dump(selected_copy, f)
        except Exception:
            self.logger.exception("Failed to persist excluded countries")

    def _load_persisted(self) -> Optional[list[str]]:
        try:
            if os.path.exists(self._store_path):
                with open(self._store_path, encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return [c.upper() for c in data if isinstance(c, str)]
        except Exception:
            self.logger.exception("Failed to load persisted excluded countries")
        return None

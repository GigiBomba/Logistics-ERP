import time
from typing import Any, Dict, List, Optional, Tuple


class AnalyticsService:
    CACHE_TTL = 30.0

    def __init__(self, db):
        self.db = db
        self._cache: Optional[Tuple[Any, Any, Any]] = None
        self._cache_ts: float = 0.0
        self._cache_key: Optional[Tuple[str, str]] = None

    def get_data(self, from_date=None, to_date=None) -> tuple:
        now = time.time()
        key = (from_date or "", to_date or "")
        if self._cache and self._cache_key == key and (now - self._cache_ts) < self.CACHE_TTL:
            return self._cache
        self._cache = self.db.get_analytics_data(from_date, to_date)
        self._cache_ts = now
        self._cache_key = key
        return self._cache

    def invalidate(self):
        self._cache = None
        self._cache_ts = 0.0
        self._cache_key = None

import time
from typing import Any, Dict, List, Optional, Tuple


class AnalyticsService:
    CACHE_TTL = 30.0

    def __init__(self, db):
        self.db = db
        self._cache: Optional[Tuple[Any, Any, Any]] = None
        self._cache_ts: float = 0.0

    def get_data(self) -> tuple:
        now = time.time()
        if self._cache and (now - self._cache_ts) < self.CACHE_TTL:
            return self._cache
        self._cache = self.db.get_analytics_data()
        self._cache_ts = now
        return self._cache

    def invalidate(self):
        self._cache = None
        self._cache_ts = 0.0

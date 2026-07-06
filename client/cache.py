import time
from typing import Any, Dict, Optional

class LocalCache:
    def __init__(self, ttl: int = 300):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() - entry["time"] > self._ttl:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value: Any) -> None:
        self._store[key] = {"value": value, "time": time.time()}

    def invalidate(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()

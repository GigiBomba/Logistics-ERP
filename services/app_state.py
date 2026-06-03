"""Centralized application state management.

Replaces scattered global variables and provides a single source of truth for:
- current language
- current currency
- active route data
- selected trip
- active filters
- user preferences
"""
from typing import Any, Callable, Dict, List, Optional


class AppState:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._state: Dict[str, Any] = {}
        self._listeners: Dict[str, List[Callable]] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._state[key] = value
        self._notify(key, value)

    def subscribe(self, key: str, callback: Callable) -> None:
        if key not in self._listeners:
            self._listeners[key] = []
        self._listeners[key].append(callback)

    def unsubscribe(self, key: str, callback: Callable) -> None:
        listeners = self._listeners.get(key, [])
        if callback in listeners:
            listeners.remove(callback)

    def _notify(self, key: str, value: Any) -> None:
        import logging
        logger = logging.getLogger(__name__)
        for cb in self._listeners.get(key, []):
            try:
                cb(value)
            except Exception as e:
                logger.error("Error in AppState listener for %s: %s", key, e)

"""Centralized application state management.

Replaces scattered global variables and provides a single source of truth for:
- current language
- current currency
- active route data
- selected trip
- active filters
- user preferences
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)


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
        self._lock = threading.Lock()
        self._state: dict[str, Any] = {}
        self._listeners: dict[str, list[Callable]] = {}

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._state.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._state[key] = value
            callbacks = list(self._listeners.get(key, []))
        for cb in callbacks:
            try:
                cb(value)
            except Exception:
                logger.warning("AppState listener failed for '%s'", key, exc_info=True)

    def subscribe(self, key: str, callback: Callable) -> None:
        with self._lock:
            if key not in self._listeners:
                self._listeners[key] = []
            self._listeners[key].append(callback)

    def unsubscribe(self, key: str, callback: Callable) -> None:
        with self._lock:
            listeners = self._listeners.get(key, [])
            if callback in listeners:
                listeners.remove(callback)

    def _notify(self, key: str, value: Any) -> None:
        with self._lock:
            callbacks = list(self._listeners.get(key, []))
        for cb in callbacks:
            try:
                cb(value)
            except Exception:
                logger.warning("AppState listener failed for '%s'", key, exc_info=True)

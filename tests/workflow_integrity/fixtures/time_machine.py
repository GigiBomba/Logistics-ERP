"""TimeMachine — manipulates time for testing scheduled workflows.

Supports freezing time, advancing by intervals, and restoring real time
for tests that depend on scheduled events (dunning, maintenance, invoice aging).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch


class TimeMachine:
    """Context manager for time manipulation in tests."""

    def __init__(self, frozen_time: str | None = None):
        self._frozen = datetime.fromisoformat(frozen_time) if frozen_time else datetime.now()
        self._patches: list = []

    def freeze(self, time_str: str) -> None:
        """Freeze time to a specific ISO datetime string."""
        self._frozen = datetime.fromisoformat(time_str)
        self._patches.append(patch("datetime.datetime", wraps=datetime))
        self._patches[-1].start()
        import datetime as dt_module
        dt_module.datetime.now = lambda tz=None: self._frozen if tz is None else self._frozen.astimezone(tz)

    def advance(self, days: int = 0, hours: int = 0, minutes: int = 0) -> None:
        """Advance frozen time by the given duration."""
        delta = timedelta(days=days, hours=hours, minutes=minutes)
        self._frozen += delta

    def travel_to(self, time_str: str) -> None:
        """Jump to a specific time."""
        self._frozen = datetime.fromisoformat(time_str)

    def restore(self) -> None:
        """Restore real time by stopping all patches."""
        for p in self._patches:
            p.stop()
        self._patches.clear()

    def now(self) -> datetime:
        return self._frozen

    def __enter__(self) -> TimeMachine:
        return self

    def __exit__(self, *args: Any) -> None:
        self.restore()

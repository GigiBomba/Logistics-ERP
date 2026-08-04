"""SyncController — orchestrates synchronization between simulated platforms.

Manages offline queues, triggers sync, and verifies cross-platform state convergence.
"""

from __future__ import annotations

from typing import Any
from .multi_platform_client import DesktopClient, MobileClient


class SyncController:
    """Orchestrates cross-platform sync scenarios."""

    def __init__(self, desktop: DesktopClient, mobile: MobileClient):
        self.desktop = desktop
        self.mobile = mobile

    def dispatch_from_desktop(self, trip_id: int) -> None:
        """Desktop dispatches a trip — mobile should see it."""
        pass  # Verify mobile.get_trip(trip_id) returns same data

    def mobile_offline_update(self, trip_id: int, new_status: str) -> int:
        """Mobile updates status while offline. Returns queue size."""
        self.mobile.update_status(trip_id, new_status, offline=True)
        return self.mobile.pending_actions()

    def mobile_sync(self) -> list[bool]:
        """Replay all queued mobile actions and return results."""
        return self.mobile.sync_queue()

    def verify_convergence(self, trip_id: int) -> bool:
        """Verify both platforms see the same trip state."""
        d = self.desktop.get_trip(trip_id)
        m = self.mobile.get_trip(trip_id)
        if d is None and m is None:
            return True
        if d is None or m is None:
            return False
        return d["status"] == m["status"]

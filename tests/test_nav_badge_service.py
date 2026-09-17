"""Unit tests for MainWindow._refresh_nav_badges.

The refresh path is the repo WorkerPool pattern: both repo reads run off the
GUI thread and the result callback pushes the counts into ``nav.set_badge``.
These tests stub the repos and run the WorkerPool callback synchronously for
deterministic assertions.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.main_window import MainWindow


class _FakeNav:
    """Minimal nav recording ``set_badge`` calls."""

    def __init__(self):
        self.badges: dict[str, int] = {}

    def set_badge(self, key: str, count: int):
        self.badges[key] = count


def _make_window(trip_count=3, invoice_count=2):
    trip_repo = MagicMock()
    trip_repo.get_active_excluding_statuses.return_value = [{"id": i} for i in range(trip_count)]
    invoice_repo = MagicMock()
    invoice_repo.get_unpaid_with_client_trip_data.return_value = [{"id": i} for i in range(invoice_count)]
    nav = _FakeNav()
    return SimpleNamespace(
        trip_repo=trip_repo,
        invoice_repo=invoice_repo,
        nav=nav,
        _shutting_down=False,
    )


def _synchronous_run(monkeypatch):
    """Patch WorkerPool.run to invoke ``on_result`` inline on the GUI thread."""
    def _fake_run(fn, on_result=None, on_error=None, priority=0):
        result = fn()
        if on_result:
            on_result(result)
        return None

    monkeypatch.setattr("ui.main_window.WorkerPool.run", _fake_run)


class TestRefreshNavBadges:
    def test_sets_dispatch_and_invoice_badges(self, monkeypatch):
        """Counts flow from repos into set_badge for both nav items."""
        window = _make_window(trip_count=3, invoice_count=2)
        _synchronous_run(monkeypatch)

        MainWindow._refresh_nav_badges(window)

        assert window.nav.badges == {"dispatch_board": 3, "invoices": 2}
        window.trip_repo.get_active_excluding_statuses.assert_called_once_with(
            exclude_statuses=["Delivered", "Completed", "Done", "Cancelled", "Paid"],
        )
        window.invoice_repo.get_unpaid_with_client_trip_data.assert_called_once_with()

    def test_zero_counts_are_still_pushed(self, monkeypatch):
        """Empty repo results push 0 badges (sidebar hides at <=0)."""
        window = _make_window(trip_count=0, invoice_count=0)
        _synchronous_run(monkeypatch)

        MainWindow._refresh_nav_badges(window)

        assert window.nav.badges == {"dispatch_board": 0, "invoices": 0}

    def test_no_op_without_repos(self, monkeypatch):
        """Degraded/remote windows with no repos never schedule work."""
        window = SimpleNamespace(
            trip_repo=None,
            invoice_repo=None,
            nav=_FakeNav(),
            _shutting_down=False,
        )
        _synchronous_run(monkeypatch)

        MainWindow._refresh_nav_badges(window)

        assert window.nav.badges == {}

    def test_result_ignored_after_shutdown(self, monkeypatch):
        """Late WorkerPool results must not touch the nav post-shutdown."""
        window = _make_window(trip_count=3, invoice_count=2)
        window._shutting_down = True
        _synchronous_run(monkeypatch)

        MainWindow._refresh_nav_badges(window)

        assert window.nav.badges == {}
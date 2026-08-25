"""Tests for CountryAvoidanceManager."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, call, mock_open, patch

import pytest

from services.country_avoidance import CountryAvoidanceManager


@pytest.fixture
def manager():
    with patch("services.country_avoidance.os.path.exists", return_value=False):
        m = CountryAvoidanceManager(default_selected=[])
    return m


def test_get_all_countries(manager):
    countries = manager.get_all_countries()
    assert isinstance(countries, dict)
    assert "RO" in countries
    assert "DE" in countries
    assert countries["RO"] == "Romania"


def test_get_selected_empty(manager):
    assert manager.get_selected() == []


def test_set_selected(manager):
    manager.set_selected(["ro", "DE"])
    selected = manager.get_selected()
    assert selected == ["RO", "DE"]


def test_toggle_add(manager):
    manager.toggle("FR")
    assert "FR" in manager.get_selected()


def test_toggle_remove(manager):
    manager.set_selected(["FR", "DE"])
    manager.toggle("FR")
    assert manager.get_selected() == ["DE"]


def test_clear(manager):
    manager.set_selected(["FR", "DE"])
    manager.clear()
    assert manager.get_selected() == []


def test_default_selected_normalized():
    with patch("services.country_avoidance.os.path.exists", return_value=False):
        m = CountryAvoidanceManager(default_selected=["ro", "DE", ""])
    assert m.get_selected() == ["RO", "DE"]


def test_thread_safety():
    """Toggle from multiple threads doesn't corrupt internal list."""
    import threading
    with patch("services.country_avoidance.os.path.exists", return_value=False):
        m = CountryAvoidanceManager(default_selected=[])

    errors = []

    def toggle_code(code):
        try:
            for _ in range(100):
                m.toggle(code)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=toggle_code, args=("RO",)),
               threading.Thread(target=toggle_code, args=("DE",)),
               threading.Thread(target=toggle_code, args=("FR",))]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    # State should be consistent
    selected = m.get_selected()
    assert isinstance(selected, list)
    assert len(selected) == len(set(selected))  # no duplicates


@patch("services.country_avoidance.open", new_callable=mock_open)
@patch("services.country_avoidance.os.makedirs")
@patch("services.country_avoidance.os.path.exists", return_value=False)
def test_persist_on_set(mock_exists, mock_makedirs, mock_file, manager):
    manager.set_selected(["RO"])
    mock_file.assert_called_once()
    handle = mock_file()
    written = "".join(call[0][0] for call in handle.write.call_args_list if call[0])
    assert "RO" in written


@patch("services.country_avoidance.open", new_callable=mock_open, read_data='["RO", "DE"]')
@patch("services.country_avoidance.os.path.exists", return_value=True)
def test_load_persisted(mock_exists, mock_file):
    m = CountryAvoidanceManager(default_selected=[])
    assert m.get_selected() == ["RO", "DE"]


@patch("services.country_avoidance.open", new_callable=mock_open, read_data='{"invalid"}')
@patch("services.country_avoidance.os.path.exists", return_value=True)
def test_load_persisted_invalid_json(mock_exists, mock_file):
    m = CountryAvoidanceManager(default_selected=["FR"])
    assert m.get_selected() == ["FR"]


# ── Additional tests ───────────────────────────────────────────────

class TestManagerAdditional:
    def test_toggle_adds_and_removes(self):
        with patch("services.country_avoidance.os.path.exists", return_value=False):
            m = CountryAvoidanceManager(default_selected=["RO"])
        m.toggle("RO")  # remove
        assert "RO" not in m.get_selected()
        m.toggle("RO")  # add again
        assert "RO" in m.get_selected()

    def test_get_all_countries_returns_copy(self):
        """Modifying the returned dict should not affect the class dict."""
        with patch("services.country_avoidance.os.path.exists", return_value=False):
            m = CountryAvoidanceManager(default_selected=[])
        countries = m.get_all_countries()
        countries["XX"] = "Test"
        assert "XX" not in CountryAvoidanceManager.EUROPEAN_COUNTRIES

    def test_toggle_normalizes_to_upper(self):
        with patch("services.country_avoidance.os.path.exists", return_value=False):
            m = CountryAvoidanceManager(default_selected=[])
        m.toggle("ro")
        assert "RO" in m.get_selected()
        assert "ro" not in m.get_selected()

    def test_set_selected_ignores_none_strings(self):
        with patch("services.country_avoidance.os.path.exists", return_value=False):
            m = CountryAvoidanceManager(default_selected=[])
        m.set_selected(["RO", None, "", "DE", 123])  # type: ignore[list-item]
        assert m.get_selected() == ["RO", "DE"]

    @patch("services.country_avoidance.os.makedirs")
    @patch("services.country_avoidance.open", new_callable=mock_open)
    @patch("services.country_avoidance.os.path.exists", return_value=False)
    def test_clear_persists(self, mock_exists, mock_file, mock_makedirs):
        """clear() should write empty list to persistence."""
        m = CountryAvoidanceManager(default_selected=["FR"])
        m.clear()
        # Should write to the store
        handle = mock_file()
        written = "".join(call[0][0] for call in handle.write.call_args_list if call[0])
        assert "[]" in written or written.strip() == ""

    @patch("services.country_avoidance.open", new_callable=mock_open, read_data='["RO", "DE", "invalid')
    @patch("services.country_avoidance.os.path.exists", return_value=True)
    def test_load_persisted_malformed_json_uses_default(self, mock_exists, mock_file):
        """Malformed persisted JSON should fall back to default."""
        m = CountryAvoidanceManager(default_selected=["FR"])
        assert m.get_selected() == ["FR"]

    @patch("services.country_avoidance.open", new_callable=mock_open, read_data='["RO", "DE"]')
    @patch("services.country_avoidance.os.path.exists", return_value=True)
    def test_load_persisted_does_not_raise(self, mock_exists, mock_file):
        """Loading persisted data should not raise any exceptions."""
        try:
            m = CountryAvoidanceManager(default_selected=[])
            assert m.get_selected() == ["RO", "DE"]
        except Exception:
            pytest.fail("Loading persisted data raised an exception")

    def test_persist_failure_does_not_raise(self):
        """If writing to disk fails, the manager should not raise."""
        with patch("services.country_avoidance.os.path.exists", return_value=False), \
             patch("services.country_avoidance.open", side_effect=PermissionError("denied")):
            m = CountryAvoidanceManager(default_selected=["FR"])
            m.set_selected(["DE"])  # should not raise

    @patch("services.country_avoidance.os.path.exists", return_value=False)
    def test_default_selected_with_no_args(self, mock_exists):
        m = CountryAvoidanceManager()
        assert m.get_selected() == []

    def test_toggle_twice(self):
        """Toggling a country on then off returns to original state."""
        with patch("services.country_avoidance.os.path.exists", return_value=False):
            m = CountryAvoidanceManager(default_selected=["RO"])
        m.toggle("RO")
        m.toggle("RO")
        assert m.get_selected() == ["RO"]

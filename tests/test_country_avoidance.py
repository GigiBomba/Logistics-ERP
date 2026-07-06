"""Tests for CountryAvoidanceManager."""
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

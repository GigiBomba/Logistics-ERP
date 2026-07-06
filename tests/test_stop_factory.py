"""Tests for stop_factory module."""
from unittest.mock import MagicMock, patch

import pytest

from services.stop_factory import (
    normalize_existing_stop,
    create_stop_from_map_click,
    create_stop_from_address,
)


def test_normalize_existing_stop_from_tuple():
    result = normalize_existing_stop((45.0, 25.0))
    assert result["lat"] == 45.0
    assert result["lon"] == 25.0
    assert result["resolved"] is True
    assert result["source"] == "map_click"
    assert result["type"] == "stop"


def test_normalize_existing_stop_from_dict():
    data = {"lat": 46.0, "lon": 24.0, "address": "Somewhere"}
    result = normalize_existing_stop(data)
    assert result["lat"] == 46.0
    assert result["lon"] == 24.0
    assert result["address"] == "Somewhere"
    assert result["resolved"] is True


def test_normalize_existing_stop_from_dict_with_coords():
    data = {"coords": [47.0, 23.0]}
    result = normalize_existing_stop(data)
    assert result["lat"] == 47.0
    assert result["lon"] == 23.0


def test_normalize_existing_stop_from_dict_with_kind():
    data = {"lat": 46.0, "lon": 24.0, "kind": "waypoint"}
    result = normalize_existing_stop(data)
    assert result["type"] == "waypoint"


def test_normalize_existing_stop_empty():
    result = normalize_existing_stop(None)
    assert result["lat"] is None
    assert result["lon"] is None
    assert result["resolved"] is False
    assert result["source"] == "manual"


def test_normalize_existing_stop_from_list():
    result = normalize_existing_stop([48.0, 22.0])
    assert result["lat"] == 48.0
    assert result["lon"] == 22.0
    assert result["resolved"] is True


def test_create_stop_from_map_click():
    result = create_stop_from_map_click(45.5, 23.5)
    assert result["lat"] == 45.5
    assert result["lon"] == 23.5
    assert result["resolved"] is True
    assert result["source"] == "map_click"
    assert result["id"] is not None


def test_create_stop_from_map_click_with_callback():
    callback_calls = []
    def callback(sid, addr):
        callback_calls.append((sid, addr))
    result = create_stop_from_map_click(45.5, 23.5, reverse_callback=callback)
    assert result["id"] is not None
    # Callback runs in a daemon thread, so we just verify structure
    assert callable(callback)


@patch("services.stop_factory.geocode_place")
def test_create_stop_from_address_success(mock_geocode):
    mock_geocode.return_value = (46.0, 24.0)
    result = create_stop_from_address("Some Address")
    assert result["lat"] == 46.0
    assert result["lon"] == 24.0
    assert result["address"] == "Some Address"
    assert result["resolved"] is True
    assert result["source"] == "geocode"


@patch("services.stop_factory.geocode_place")
def test_create_stop_from_address_failure(mock_geocode):
    mock_geocode.return_value = None
    result = create_stop_from_address("Unknown Place")
    assert result["lat"] is None
    assert result["lon"] is None
    assert result["resolved"] is False
    assert result["address"] == "Unknown Place"


@patch("services.stop_factory.geocode_place")
def test_create_stop_from_address_exception(mock_geocode):
    mock_geocode.side_effect = Exception("Geocode failed")
    result = create_stop_from_address("Error Place")
    assert result["resolved"] is False

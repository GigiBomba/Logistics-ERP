"""Tests for CustomerDetector."""
import time
from unittest.mock import MagicMock, patch

import pytest

from services.document_automation.customer_detector import CustomerDetector
from services.document_automation.types import CustomerInfo


@pytest.fixture
def db_mock():
    return MagicMock()


@pytest.fixture
def detector(db_mock):
    det = CustomerDetector(db_mock)
    det.trips = MagicMock()
    det.clients = MagicMock()
    det.contacts = MagicMock()
    return det


def test_detect_for_trip_id_not_found(detector):
    detector.trips.get_by_id.return_value = None
    result = detector.detect_for_trip_id(999)
    assert result.client is None
    assert result.default_email == ""


def test_detect_for_trip_with_client_id(detector):
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client A", "email": "client@a.com", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = []
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    assert result.client["name"] == "Client A"
    assert result.default_email == "client@a.com"
    assert result.all_emails == ["client@a.com"]


def test_detect_for_trip_with_inactive_client(detector):
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Inactive Client", "email": "inactive@a.com", "is_active": 0,
    }
    detector.clients.search_by_name.return_value = [
        {"id": 2, "name": "Fallback Client", "email": "fallback@a.com", "is_active": 1},
    ]
    detector.contacts.get_by_client.return_value = []
    trip = {"id": 42, "client_id": 1, "client_name": "Fallback Client"}
    result = detector.detect_for_trip(trip)
    # Should fall through to name-based lookup
    assert result.client["name"] == "Fallback Client"


def test_detect_for_trip_name_fallback(detector):
    detector.clients.get_by_id.return_value = None
    detector.clients.search_by_name.return_value = [
        {"id": 3, "name": "Name Match", "email": "name@match.com", "is_active": 1},
    ]
    detector.contacts.get_by_client.return_value = []
    trip = {"id": 43, "client_name": "Name Match"}
    result = detector.detect_for_trip(trip)
    assert result.client["name"] == "Name Match"


def test_detect_for_trip_no_match(detector):
    detector.clients.get_by_id.return_value = None
    detector.clients.search_by_name.return_value = []
    trip = {"id": 44, "client_name": "Unknown"}
    result = detector.detect_for_trip(trip)
    assert result.client is None
    # Should not cache "not found"
    assert 44 not in detector._cache


def test_detect_for_trip_with_contacts(detector):
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client", "email": "", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = [
        {"id": 10, "email": "contact@c.com", "is_primary": 1},
        {"id": 11, "email": "secondary@c.com", "is_primary": 0},
    ]
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    # Primary contact email should be default
    assert result.default_email == "contact@c.com"
    assert len(result.all_emails) == 2


def test_cache_hit(detector):
    info = CustomerInfo(client=None, primary_contact=None, all_emails=[], default_email="")
    detector._cache[42] = (info, time.time())
    detector.clients.get_by_id = MagicMock()  # should not be called

    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    assert result is info
    detector.clients.get_by_id.assert_not_called()


def test_cache_ttl_expiry(detector):
    info = CustomerInfo(client=None, primary_contact=None, all_emails=[], default_email="")
    # Insert with old timestamp
    detector._cache[42] = (info, time.time() - 1000)  # well past TTL

    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Refreshed", "email": "r@c.com", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = []

    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    # Should have been refreshed from DB
    assert result.client["name"] == "Refreshed"
    assert 42 in detector._cache  # re-cached


def test_cache_fifo_eviction(detector):
    detector._cache_max = 2
    info = CustomerInfo(client=None, primary_contact=None, all_emails=[], default_email="")
    detector._cache_put(1, info)
    detector._cache_put(2, info)
    assert 1 in detector._cache
    assert 2 in detector._cache
    detector._cache_put(3, info)
    # 1 should be evicted
    assert 1 not in detector._cache
    assert 3 in detector._cache


def test_cache_duplicate_put(detector):
    info = CustomerInfo(client=None, primary_contact=None, all_emails=[], default_email="")
    detector._cache_put(1, info)
    detector._cache_put(1, info)  # should not add duplicate
    assert len(detector._cache_order) == 1


def test_invalidate_cache(detector):
    detector._cache[1] = ("data", time.time())
    detector._cache_order.append(1)
    detector.invalidate_cache()
    assert detector._cache == {}
    assert detector._cache_order == []


def test_invalidate_trip(detector):
    detector._cache[1] = ("data", time.time())
    detector._cache_order.append(1)
    detector.invalidate_trip(1)
    assert 1 not in detector._cache


def test_detect_for_trip_no_id_no_cache(detector):
    detector.clients.get_by_id.return_value = None
    detector.clients.search_by_name.return_value = []
    trip = {"client_name": "No ID Trip"}
    result = detector.detect_for_trip(trip)
    assert result.client is None

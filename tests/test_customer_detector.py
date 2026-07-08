"""Tests for CustomerDetector."""
from __future__ import annotations

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


def test_detect_for_trip_invalid_client_id(detector):
    """Non-numeric client_id should not crash and should fall through to name match."""
    detector.clients.get_by_id.side_effect = (TypeError,)
    detector.clients.search_by_name.return_value = [
        {"id": 3, "name": "Name Match", "email": "name@match.com", "is_active": 1},
    ]
    detector.contacts.get_by_client.return_value = []
    trip = {"id": 45, "client_id": "not-a-number", "client_name": "Name Match"}
    result = detector.detect_for_trip(trip)
    assert result.client["name"] == "Name Match"


def test_detect_for_trip_client_email_without_contacts(detector):
    """When client has email but no contacts, default_email should be the client's email."""
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client", "email": "client@a.com", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = []
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    assert result.default_email == "client@a.com"
    assert result.all_emails == ["client@a.com"]


def test_detect_for_trip_deduplicate_emails(detector):
    """Duplicate emails across client and contacts should be deduplicated."""
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client", "email": "same@email.com", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = [
        {"id": 10, "email": "same@email.com", "is_primary": 1},
        {"id": 11, "email": "other@email.com", "is_primary": 0},
    ]
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    assert len(result.all_emails) == 2
    assert "same@email.com" in result.all_emails
    assert "other@email.com" in result.all_emails


def test_detect_for_trip_contacts_no_primary(detector):
    """When no contact is marked as primary, the first contact should become default."""
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client", "email": "", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = [
        {"id": 10, "email": "first@c.com", "is_primary": 0},
        {"id": 11, "email": "second@c.com", "is_primary": 0},
    ]
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    assert result.default_email == "first@c.com"


def test_detect_for_trip_search_by_name_exception(detector):
    """Exception in search_by_name should not crash; returns empty info."""
    detector.clients.get_by_id.return_value = None
    detector.clients.search_by_name.side_effect = Exception("DB error")
    trip = {"id": 46, "client_name": "Some Client"}
    result = detector.detect_for_trip(trip)
    assert result.client is None
    assert result.default_email == ""


def test_detect_for_trip_no_id_no_name(detector):
    """Trip with no client_id and no client_name should return empty info."""
    trip = {"id": 47}
    result = detector.detect_for_trip(trip)
    assert result.client is None
    assert result.default_email == ""


def test_detect_for_trip_contacts_exception(detector):
    """Exception during contact lookup should not crash."""
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client", "email": "client@a.com", "is_active": 1,
    }
    detector.contacts.get_by_client.side_effect = Exception("Contact error")
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    assert result.client["name"] == "Client"
    assert result.all_emails == ["client@a.com"]


def test_cache_get_expired_returns_none_and_cleans(detector):
    """_cache_get should return None for expired entries and clean them up."""
    info = CustomerInfo(client=None, primary_contact=None, all_emails=[], default_email="")
    detector._cache[99] = (info, time.time() - 1000)  # expired
    detector._cache_order.append(99)
    result = detector._cache_get(99)
    assert result is None
    assert 99 not in detector._cache
    assert 99 not in detector._cache_order


def test_cache_hit_refreshes_ttl(detector):
    """A cache hit should refresh the TTL timestamp."""
    info = CustomerInfo(client=None, primary_contact=None, all_emails=[], default_email="")
    old_ts = time.time() - 60
    detector._cache[42] = (info, old_ts)
    detector._cache_get(42)
    # TTL should be refreshed
    _, new_ts = detector._cache[42]
    assert new_ts > old_ts


def test_detect_for_trip_primary_contact_no_email(detector):
    """When primary contact has no email, fall back to client email."""
    detector.clients.get_by_id.return_value = {
        "id": 1, "name": "Client", "email": "client@a.com", "is_active": 1,
    }
    detector.contacts.get_by_client.return_value = [
        {"id": 10, "email": "", "is_primary": 1},
        {"id": 11, "email": "other@c.com", "is_primary": 0},
    ]
    trip = {"id": 42, "client_id": 1}
    result = detector.detect_for_trip(trip)
    # Client email should be default since primary has none
    assert result.default_email == "client@a.com"
    assert "other@c.com" in result.all_emails

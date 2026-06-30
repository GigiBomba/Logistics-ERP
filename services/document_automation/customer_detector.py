"""Customer detection.

When a trip is matched, identify the customer behind it and surface
their contact email addresses.  The customer is looked up via the
trip's ``client_id`` column first, then by fuzzy-matching
``trip.client_name`` against the ``clients`` table.
"""

from __future__ import annotations

import contextlib
import logging
import threading
import time
from typing import Any

from repositories.client_repository import ClientRepository
from repositories.contact_repository import ContactRepository
from repositories.trip_repository import TripRepository

from .types import CustomerInfo

logger = logging.getLogger("document_automation.customer_detector")


class CustomerDetector:
    """Stateless detector — safe to call from worker threads.

    Maintains a small bounded cache of resolved customers so that a
    pipeline processing many documents for the same trip doesn't hit
    the database on every call.  ``invalidate_cache()`` can be called
    after a client or contact is edited to drop stale entries.
    """

    # Default: cache at most 200 customer lookups for 5 minutes.
    DEFAULT_CACHE_MAX_ENTRIES = 200
    DEFAULT_CACHE_TTL_S = 300

    def __init__(self, db, *,
                 cache_max_entries: int = DEFAULT_CACHE_MAX_ENTRIES,
                 cache_ttl_s: float = DEFAULT_CACHE_TTL_S) -> None:
        self.db = db
        self.trips = TripRepository(db)
        self.clients = ClientRepository(db)
        self.contacts = ContactRepository(db)
        self._cache_max = cache_max_entries
        self._cache_ttl = cache_ttl_s
        self._lock = threading.Lock()
        # Stored as ``{trip_id: (info, inserted_at)}`` so we can apply TTL.
        self._cache: dict[int, Any] = {}
        self._cache_order: list[int] = []  # FIFO eviction order

    def _cache_get(self, trip_id: int) -> CustomerInfo | None:
        with self._lock:
            entry = self._cache.get(trip_id)
            if entry is None:
                return None
            info, inserted_at = entry
            if (time.time() - inserted_at) > self._cache_ttl:
                self._cache.pop(trip_id, None)
                with contextlib.suppress(ValueError):
                    self._cache_order.remove(trip_id)
                return None
            # Refresh TTL on hit so frequently accessed entries stay valid.
            self._cache[trip_id] = (info, time.time())
            return info

    def _cache_put(self, trip_id: int, info: CustomerInfo) -> None:
        with self._lock:
            if trip_id in self._cache:
                return
            if len(self._cache) >= self._cache_max:
                # FIFO eviction — drop the oldest entry.
                oldest = self._cache_order.pop(0)
                self._cache.pop(oldest, None)
            self._cache[trip_id] = (info, time.time())
            self._cache_order.append(trip_id)

    def detect_for_trip_id(self, trip_id: int) -> CustomerInfo:
        trip = self.trips.get_by_id(trip_id)
        if not trip:
            return CustomerInfo(None, None, [], "")
        return self.detect_for_trip(trip)

    def detect_for_trip(self, trip: dict[str, Any]) -> CustomerInfo:
        if trip.get("id") is not None:
            cached = self._cache_get(int(trip["id"]))
            if cached is not None:
                return cached

        client: dict[str, Any] | None = None
        client_id = trip.get("client_id")
        if client_id:
            try:
                client = self.clients.get_by_id(int(client_id))
            except (TypeError, ValueError):
                client = None
                logger.debug("Trip %s has invalid client_id: %r", trip.get("id"), client_id)
            if client and not client.get("is_active", 1):
                # Soft-deleted — fall through to name-based lookup so the
                # user can still match by name.
                logger.debug(
                    "Trip %s: client_id %s is inactive, falling back to name match",
                    trip.get("id"), client_id,
                )
                client = None

        if client is None and trip.get("client_name"):
            try:
                matches = self.clients.search_by_name(
                    trip["client_name"], fuzzy=True, limit=5,
                )
            except Exception:
                matches = []
                logger.exception("Client search failed for %r", trip.get("client_name"))
            if matches:
                client = matches[0]

        if client is None:
            # Don't cache "not found" — the user may add the client and
            # re-run.  Returning early avoids polluting the cache with
            # a stale negative result.
            return CustomerInfo(None, None, [], "")

        # Load contacts for this client.
        try:
            contacts = self.contacts.get_by_client(int(client["id"]))
        except Exception:
            contacts = []
            logger.exception("Contact lookup failed for client %s", client.get("id"))

        primary: dict[str, Any] | None = None
        for c in contacts:
            if c.get("is_primary") == 1:
                primary = c
                break
        if primary is None and contacts:
            primary = contacts[0]

        # Build a deduplicated, non-empty list of email addresses.
        all_emails: list[str] = []
        for source in (client, primary, *(c for c in contacts if c is not primary)):
            email = (source.get("email") or "").strip() if source else ""
            if email and email not in all_emails:
                all_emails.append(email)

        default_email = ""
        if client and (client.get("email") or "").strip():
            default_email = (client.get("email") or "").strip()
        elif primary and (primary.get("email") or "").strip():
            default_email = (primary.get("email") or "").strip()
        elif all_emails:
            default_email = all_emails[0]

        info = CustomerInfo(
            client=client,
            primary_contact=primary,
            all_emails=all_emails,
            default_email=default_email,
        )
        if trip.get("id") is not None:
            self._cache_put(int(trip["id"]), info)
        return info

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_order.clear()

    def invalidate_trip(self, trip_id: int) -> None:
        """Drop a single trip's cached entry (e.g. when its client_id changes)."""
        with self._lock:
            self._cache.pop(trip_id, None)
            with contextlib.suppress(ValueError):
                self._cache_order.remove(trip_id)

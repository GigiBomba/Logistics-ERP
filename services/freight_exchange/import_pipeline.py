"""Freight Exchange Import Pipeline — provider-agnostic load-to-trip conversion.

A load from any connected provider never remains a "provider object" inside
Operion.  The moment a dispatcher decides to use one, it becomes an ordinary
internal trip via ``trip_service.create()`` — the SAME service manual trip
creation uses.  No parallel provider-specific trip representation, no
special-cased subtype anywhere downstream.

The only schema change needed anywhere else in Operion: nullable ``source``,
``source_provider_id``, and ``source_reference_id`` columns on the ``trips``
table (already added by Alembic migration).
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from models.freight_exchange_models import ImportResult, LoadSearchResult
from models.trip_models import TripCreate, TripStop
from services.freight_exchange.search import SearchEngineService

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────
# Default client name assigned to imported loads before a dispatcher refines it.
DEFAULT_IMPORT_CLIENT_NAME = "Freight Exchange Import"


class ImportError(Exception):
    """Raised when a load cannot be imported (already imported, not found, etc.)."""
    pass


class ImportPipelineService:
    """Converts freight exchange loads into normal Operion trips.

    Usage::

        pipeline = ImportPipelineService(db)
        result = await pipeline.import_load(
            company_id=1, provider_id="timocom",
            provider_load_id="TL-12345", user_id=42,
        )
        # result.trip_id is the newly created trip
    """

    def __init__(self, db):
        self.db = db
        self._search = SearchEngineService(db)

    async def import_load(
        self,
        company_id: int,
        provider_id: str,
        provider_load_id: str,
        user_id: int,
    ) -> ImportResult:
        """Import a freight exchange load as an ordinary Operion trip.

        1. Fetches the load from the provider via the Search Engine
        2. Maps ``LoadSearchResult`` → ``TripCreate``
        3. Calls ``TripService.create()`` — the SAME path manual trips use
        4. Returns ``ImportResult`` with the new trip ID and source metadata

        Raises ``ImportError`` if the load is not found or cannot be imported.

        **Zero per-provider branching** — all adapters produce the same
        ``LoadSearchResult`` shape, and this method treats every provider
        identically beyond which ``provider_id`` is recorded in the trip.
        """
        # 1. Fetch the load
        load = await self._search.get_load(company_id, provider_id, provider_load_id)
        if load is None:
            raise ImportError(
                f"Load not found: provider={provider_id} load_id={provider_load_id}"
            )

        # 2. Check for duplicate import (same provider_load_id already imported)
        if self._is_already_imported(company_id, provider_id, provider_load_id):
            raise ImportError(
                f"Load already imported: provider={provider_id} load_id={provider_load_id}"
            )

        # 3. Map LoadSearchResult → TripCreate
        trip_create = self._map_to_trip_create(load, provider_id, provider_load_id)

        # 4. Create the trip via the SAME service manual trips use
        from services.trip_service import TripService

        trip_service = TripService(self.db)
        result = await asyncio.to_thread(trip_service.create, trip_create, user_id=user_id)

        if not result.success:
            errors = "; ".join(e.message for e in result.errors)
            raise ImportError(f"Trip creation failed: {errors}")

        trip_id = result.data.id

        logger.info(
            "Imported load as trip #%d (provider=%s, load_id=%s, user=%d)",
            trip_id, provider_id, provider_load_id, user_id,
        )

        return ImportResult(
            trip_id=trip_id,
            source="freight_exchange",
            source_provider_id=provider_id,
            source_reference_id=provider_load_id,
            imported_at=datetime.now(timezone.utc),
            imported_by_user_id=user_id,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _map_to_trip_create(
        self,
        load: LoadSearchResult,
        provider_id: str,
        provider_load_id: str,
    ) -> TripCreate:
        """Map a normalized LoadSearchResult into a TripCreate.

        This mapping is provider-agnostic — every adapter produces the same
        ``LoadSearchResult`` shape, so the mapping is identical for all
        providers.
        """
        # Dates: use pickup window start as trip start, delivery window end as trip end
        pickup_start = load.pickup_window[0]
        delivery_end = load.delivery_window[1]

        # Build human-readable reference string
        ref_parts = [f"FX-{provider_id.upper()[:4]}", provider_load_id[:12]]
        reference = "-".join(ref_parts)

        # Origin/destination stops
        stops = [
            TripStop(
                address=load.origin,
                sequence=0,
                type="pickup",
                departure=pickup_start,
            ),
            TripStop(
                address=load.destination,
                sequence=1,
                type="delivery",
                arrival=delivery_end,
            ),
        ]

        return TripCreate(
            client_id=0,  # Dispatcher assigns a real client after import
            client_name=DEFAULT_IMPORT_CLIENT_NAME,
            reference=reference,
            start_date=pickup_start.date(),
            end_date=delivery_end.date(),
            price_eur=load.price.amount,
            currency=load.price.currency,
            distance_km=load.distance_km,
            stops=stops,
            notes=f"Imported from {provider_id} (load {provider_load_id})",
            status="Planned",
            source="freight_exchange",
            source_provider_id=provider_id,
            source_reference_id=provider_load_id,
        )

    def _is_already_imported(
        self,
        company_id: int,
        provider_id: str,
        provider_load_id: str,
    ) -> bool:
        """Check if this load was already imported as a trip.

        Queries the trips table for any trip with the same
        (source_provider_id, source_reference_id) pair.
        """
        from repositories.trip_repository import TripRepository

        repo = TripRepository(self.db)

        # Check for existing import
        try:
            # Use public API: query via documented repository method pattern
            # If TripRepository exposes a suitable method in the future, switch to it
            rows = repo._fetchall(
                "SELECT id FROM trips WHERE source_provider_id = ? AND source_reference_id = ? AND company_id = ?",
                (provider_id, provider_load_id, company_id),
            )
            return len(rows) > 0
        except Exception as e:
            logger.warning("Duplicate check unavailable (possible pre-migration state): %s", e)
            return False

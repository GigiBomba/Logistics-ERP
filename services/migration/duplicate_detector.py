"""Fuzzy duplicate detection with per-entity matching strategies.

Each entity type has a dedicated detection method tuned to the most
reliable dedup signals for that domain (e.g. plate+vin for trucks,
CMR number for trips, name for clients).
"""

from __future__ import annotations

import difflib
import logging
from typing import Any

from database.db_manager import DatabaseManager
from services.migration.types import DuplicateCandidate, EntityType

logger = logging.getLogger(__name__)

_FUZZY_THRESHOLD = 0.85
_VAT_BOOST = 0.30


class DuplicateDetector:
    """Detect duplicate records across entity types using configurable strategies."""

    def __init__(self, db: DatabaseManager) -> None:
        self.db = db

    def find_duplicates(
        self,
        row: dict[str, Any],
        entity_type: EntityType,
    ) -> list[DuplicateCandidate]:
        """Dispatch to the appropriate per-entity detection method."""
        dispatcher = {
            EntityType.CLIENT: self._find_client_duplicates,
            EntityType.TRUCK: self._find_truck_duplicates,
            EntityType.DRIVER: self._find_driver_duplicates,
            EntityType.TRIP: self._find_trip_duplicates,
            EntityType.INVOICE: self._find_invoice_duplicates,
            EntityType.DOCUMENT: self._find_document_duplicates,
        }
        method = dispatcher.get(entity_type)
        if method is None:
            logger.warning("No duplicate detection for entity type: %s", entity_type)
            return []
        try:
            return method(row)
        except Exception as exc:
            logger.exception("Duplicate detection failed for %s: %s", entity_type, exc)
            return []

    # ── Per-entity strategies ──────────────────────────────────────────

    def _find_client_duplicates(self, row: dict[str, Any]) -> list[DuplicateCandidate]:
        """Find duplicate clients by exact name, fuzzy name, and VAT boost."""
        candidates: list[DuplicateCandidate] = []
        name = (row.get("name") or "").strip()
        vat = (row.get("vat_number") or "").strip()

        if not name:
            return candidates

        try:
            from repositories.client_repository import ClientRepository

            repo = ClientRepository(self.db)
        except Exception as exc:
            logger.warning("ClientRepository unavailable: %s", exc)
            return candidates

        # Exact name match
        if name:
            try:
                exact = repo.get_by_name(name)
                if exact:
                    candidates.append(
                        DuplicateCandidate(
                            existing=exact,
                            incoming=row,
                            entity_type=EntityType.CLIENT,
                            score=1.0,
                            matched_on=["name"],
                        )
                    )
                    return candidates  # Exact match is definitive
            except Exception as exc:
                logger.debug("Exact name lookup failed: %s", exc)

        # Fuzzy name match via search
        if name:
            try:
                fuzzy_matches = repo.search_by_name(name, fuzzy=True, limit=10)
                for match in fuzzy_matches:
                    existing_name = (match.get("name") or "").strip()
                    score = difflib.SequenceMatcher(
                        None, name.lower(), existing_name.lower()
                    ).ratio()

                    # Boost score if VAT numbers also match
                    if vat and match.get("vat_number"):
                        if vat.strip().lower() == (match["vat_number"] or "").strip().lower():
                            score += _VAT_BOOST

                    if score > _FUZZY_THRESHOLD:
                        candidates.append(
                            DuplicateCandidate(
                                existing=match,
                                incoming=row,
                                entity_type=EntityType.CLIENT,
                                score=min(score, 1.0),
                                matched_on=["name", "vat_number"] if vat else ["name"],
                            )
                        )
            except Exception as exc:
                logger.debug("Fuzzy client search failed: %s", exc)

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:5]

    def _find_truck_duplicates(self, row: dict[str, Any]) -> list[DuplicateCandidate]:
        """Find duplicate trucks by exact plate (case-insensitive) or VIN."""
        candidates: list[DuplicateCandidate] = []
        plate = (row.get("plate_number") or "").strip().upper()
        vin = (row.get("vin") or "").strip().upper()

        if not plate and not vin:
            return candidates

        try:
            from repositories.fleet_repository import FleetRepository

            repo = FleetRepository(self.db)
            all_trucks = repo.get_all(limit=2000)
        except Exception as exc:
            logger.warning("FleetRepository unavailable: %s", exc)
            return candidates

        for truck in all_trucks:
            matched_on: list[str] = []
            score = 0.0

            existing_plate = (truck.get("plate_number") or "").strip().upper()
            existing_vin = (truck.get("vin") or "").strip().upper()

            if plate and existing_plate and plate == existing_plate:
                score = 1.0
                matched_on.append("plate_number")
                candidates.append(
                    DuplicateCandidate(
                        existing=truck,
                        incoming=row,
                        entity_type=EntityType.TRUCK,
                        score=score,
                        matched_on=matched_on,
                    )
                )
                return candidates  # Exact plate match is definitive

            if vin and existing_vin and vin == existing_vin:
                score = 1.0
                matched_on.append("vin")
                candidates.append(
                    DuplicateCandidate(
                        existing=truck,
                        incoming=row,
                        entity_type=EntityType.TRUCK,
                        score=score,
                        matched_on=matched_on,
                    )
                )
                return candidates  # Exact VIN match is definitive

        return candidates

    def _find_driver_duplicates(self, row: dict[str, Any]) -> list[DuplicateCandidate]:
        """Find duplicate drivers by exact name match."""
        candidates: list[DuplicateCandidate] = []
        name = (row.get("name") or "").strip()

        if not name:
            return candidates

        try:
            from repositories.driver_repository import DriverRepository

            repo = DriverRepository(self.db)
            all_drivers = repo.get_all(limit=2000)
        except Exception as exc:
            logger.warning("DriverRepository unavailable: %s", exc)
            return candidates

        for driver in all_drivers:
            existing_name = (driver.get("name") or "").strip()
            if name.lower() == existing_name.lower():
                candidates.append(
                    DuplicateCandidate(
                        existing=driver,
                        incoming=row,
                        entity_type=EntityType.DRIVER,
                        score=1.0,
                        matched_on=["name"],
                    )
                )
                return candidates  # Exact name match is definitive

        return candidates

    def _find_trip_duplicates(self, row: dict[str, Any]) -> list[DuplicateCandidate]:
        """Find duplicate trips by exact CMR number."""
        candidates: list[DuplicateCandidate] = []
        cmr = (row.get("cmr_number") or "").strip()

        if not cmr:
            return candidates

        try:
            from repositories.trip_repository import TripRepository

            repo = TripRepository(self.db)
            matches = repo._fetchall(
                "SELECT * FROM trips WHERE cmr_number = ?",
                (cmr,),
            )
        except Exception as exc:
            logger.warning("TripRepository lookup failed: %s", exc)
            return candidates

        for match in matches:
            candidates.append(
                DuplicateCandidate(
                    existing=match,
                    incoming=row,
                    entity_type=EntityType.TRIP,
                    score=1.0,
                    matched_on=["cmr_number"],
                )
            )

        return candidates

    def _find_invoice_duplicates(self, row: dict[str, Any]) -> list[DuplicateCandidate]:
        """Find duplicate invoices by exact invoice number."""
        candidates: list[DuplicateCandidate] = []
        inv_num = (row.get("invoice_number") or "").strip()

        if not inv_num:
            return candidates

        try:
            from repositories.invoice_repository import InvoiceRepository

            repo = InvoiceRepository(self.db)
            match = repo.get_by_number(inv_num)
        except Exception as exc:
            logger.warning("InvoiceRepository lookup failed: %s", exc)
            return candidates

        if match:
            candidates.append(
                DuplicateCandidate(
                    existing=match,
                    incoming=row,
                    entity_type=EntityType.INVOICE,
                    score=1.0,
                    matched_on=["invoice_number"],
                )
            )

        return candidates

    def _find_document_duplicates(self, row: dict[str, Any]) -> list[DuplicateCandidate]:
        """Find duplicate documents by delegating to DocumentService."""
        candidates: list[DuplicateCandidate] = []
        file_path = (row.get("file_path") or "").strip()

        if not file_path:
            return candidates

        try:
            from services.document_service import DocumentService

            doc_svc = DocumentService(self.db)
            doc_id = doc_svc.check_duplicate(file_path)
        except Exception as exc:
            logger.warning("DocumentService.check_duplicate failed: %s", exc)
            return candidates

        if doc_id is not None:
            try:
                doc = doc_svc.get_by_id(doc_id)
                if doc:
                    candidates.append(
                        DuplicateCandidate(
                            existing=doc,
                            incoming=row,
                            entity_type=EntityType.DOCUMENT,
                            score=1.0,
                            matched_on=["file_hash"],
                        )
                    )
            except Exception as exc:
                logger.debug("Could not fetch duplicate document %d: %s", doc_id, exc)

        return candidates

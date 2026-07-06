"""Client service — business logic for client management."""
import logging
from typing import Any, Optional

from repositories.client_repository import ClientRepository
from repositories.contact_repository import ContactRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.tag_repository import TagRepository
from services.operations.event_bus import EventBus

logger = logging.getLogger(__name__)


CLIENT_MERGED = "CLIENT_MERGED"


class ClientService:
    def __init__(self, db):
        self.db = db
        self._repo = ClientRepository(db)
        self._inv_repo = InvoiceRepository(db)
        self._contact_repo = ContactRepository(db)
        self._tag_repo = TagRepository(db)
        self._event_bus = EventBus()

    # ── Existing methods ─────────────────────────────────────────────────

    def get_by_id(self, client_id: int) -> Optional[dict[str, Any]]:
        return self._repo.get_by_id(client_id)

    def get_all(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        return self._repo.get_all(include_inactive=include_inactive)

    def get_all_with_revenue(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        return self._repo.get_all_with_revenue(include_inactive=include_inactive)

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._repo.search(query, limit=limit)

    def search_advanced(self, query: str, include_inactive: bool = False, limit: int = 200) -> list[dict[str, Any]]:
        return self._repo.search_advanced(query, include_inactive=include_inactive, limit=limit)

    def create(self, name: str, **kwargs) -> int:
        data = {"name": name}
        data.update(kwargs)
        return self._repo.create(data)

    def update(self, client_id: int, **kwargs) -> None:
        self._repo.update(client_id, kwargs)

    def deactivate(self, client_id: int) -> None:
        self._repo.deactivate(client_id)

    def get_trip_count(self, client_id: int) -> int:
        return self._repo.get_trip_count(client_id)

    def get_top_clients(self, limit: int = 5) -> list[dict[str, Any]]:
        return self._repo.get_top_by_revenue(limit=limit)

    def get_or_create(self, name: str) -> int:
        name = name.strip()
        if not name:
            return None
        existing = self._repo.get_by_name(name)
        if existing:
            return existing["id"]
        return self.create(name=name)

    def resolve_client_id(self, name: str) -> Optional[int]:
        name = name.strip()
        if not name:
            return None
        existing = self._repo.get_by_name(name)
        return existing["id"] if existing else None

    # ── Dashboard & queries ─────────────────────────────────────────────

    def get_client_dashboard(self, client_id: int) -> dict[str, Any]:
        client = self._repo.get_by_id(client_id)
        if not client:
            return {}
        revenue = self._repo.get_revenue_summary(client_id)
        outstanding = self._repo.get_outstanding_balance(client_id)
        recent_trips = self._repo.get_trips(client_id, limit=5)
        outstanding_invoices = self._repo.get_outstanding_invoices(client_id)
        status_counts = self._repo.get_trips_status_counts(client_id)
        last_30 = self._repo.get_trip_count_in_range(client_id, days=30)
        contacts = self._contact_repo.get_by_client(client_id)
        tags = self._tag_repo.get_by_client(client_id)
        return {
            "client": client,
            "total_revenue": revenue.get("total_revenue", 0) or 0,
            "total_profit": revenue.get("total_profit", 0) or 0,
            "avg_profit": revenue.get("avg_profit", 0) or 0,
            "total_trips": revenue.get("total_trips", 0) or 0,
            "total_km": revenue.get("total_km", 0) or 0,
            "last_trip_date": revenue.get("last_trip_date", ""),
            "outstanding_balance": outstanding,
            "trips_last_30_days": last_30,
            "recent_trips": recent_trips,
            "outstanding_invoices": outstanding_invoices,
            "status_counts": status_counts,
            "contacts": contacts,
            "tags": tags,
        }

    def get_client_trips(self, client_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self._repo.get_trips(client_id, limit=limit, offset=offset)

    def get_client_invoices(self, client_id: int, limit: int = 100) -> list[dict[str, Any]]:
        return self._repo.get_invoices(client_id, limit=limit)

    def get_client_revenue_history(self, client_id: int, months: int = 12) -> list[dict[str, Any]]:
        return self._repo.get_revenue_history(client_id, months=months)

    def get_outstanding_invoices(self, client_id: int) -> list[dict[str, Any]]:
        return self._inv_repo.get_outstanding_by_client(client_id)

    def get_outstanding_balance(self, client_id: int) -> float:
        return self._inv_repo.get_outstanding_balance(client_id)

    # ── Contact management ──────────────────────────────────────────────

    def get_contacts(self, client_id: int) -> list[dict[str, Any]]:
        return self._contact_repo.get_by_client(client_id)

    def add_contact(self, client_id: int, **kwargs) -> int:
        data = dict(kwargs)
        data["client_id"] = client_id
        return self._contact_repo.create(data)

    def update_contact(self, contact_id: int, **kwargs) -> None:
        self._contact_repo.update(contact_id, kwargs)

    def delete_contact(self, contact_id: int) -> None:
        self._contact_repo.delete(contact_id)

    def set_primary_contact(self, client_id: int, contact_id: int) -> None:
        self._contact_repo.set_primary(client_id, contact_id)

    # ── Tag management ─────────────────────────────────────────────────

    def get_tags(self, client_id: int) -> list[str]:
        rows = self._tag_repo.get_by_client(client_id)
        return [r["tag"] for r in rows]

    def add_tag(self, client_id: int, tag: str) -> None:
        self._tag_repo.add(client_id, tag)

    def remove_tag(self, client_id: int, tag: str) -> None:
        self._tag_repo.remove(client_id, tag)

    def get_all_tags(self) -> list[str]:
        return self._tag_repo.get_all_tags()

    # ── Payment tracking ────────────────────────────────────────────────

    def get_payment_summary(self, client_id: int) -> dict[str, Any]:
        row = self._inv_repo.get_payment_summary(client_id)
        if not row:
            return {
                "total_billed": 0, "total_paid": 0,
                "unpaid": 0, "overdue": 0, "invoice_count": 0,
            }
        inv_count = self._inv_repo.get_invoice_count(client_id)
        return {
            "total_billed": row.get("total_billed", 0) or 0,
            "total_paid": row.get("total_paid", 0) or 0,
            "unpaid": row.get("unpaid", 0) or 0,
            "overdue": row.get("overdue", 0) or 0,
            "invoice_count": inv_count,
        }

    # ── Merge ───────────────────────────────────────────────────────────

    def merge_clients(self, from_id: int, to_id: int) -> dict[str, int]:
        if not self.db:
            logger.error("ClientService: no database, cannot merge")
            return {"trips": 0, "invoices": 0, "contacts": 0}

        try:
            result = self._repo.merge_client_data(from_id, to_id)
            self._event_bus.publish(CLIENT_MERGED, {
                "from_id": from_id, "to_id": to_id,
                "trips": result["trips"],
            })
            return result
        except Exception:
            logger.exception("merge_clients failed")
            return {"trips": 0, "invoices": 0, "contacts": 0}

    # ── Export ──────────────────────────────────────────────────────────

    def export_clients_csv(self, include_inactive: bool = False) -> list[dict[str, Any]]:
        return self._repo.get_all_with_revenue(include_inactive=include_inactive)

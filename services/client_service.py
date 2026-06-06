"""Client service — business logic for client management."""
from typing import Any, Dict, List, Optional

from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from repositories.contact_repository import ContactRepository
from repositories.tag_repository import TagRepository
from services.operations.event_bus import EventBus


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

    def get_by_id(self, client_id: int) -> Optional[Dict[str, Any]]:
        return self._repo.get_by_id(client_id)

    def get_all(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._repo.get_all(include_inactive=include_inactive)

    def get_all_with_revenue(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._repo.get_all_with_revenue(include_inactive=include_inactive)

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._repo.search(query, limit=limit)

    def search_advanced(self, query: str, include_inactive: bool = False, limit: int = 200) -> List[Dict[str, Any]]:
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

    def get_top_clients(self, limit: int = 5) -> List[Dict[str, Any]]:
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

    def get_client_dashboard(self, client_id: int) -> Dict[str, Any]:
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

    def get_client_trips(self, client_id: int, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        return self._repo.get_trips(client_id, limit=limit, offset=offset)

    def get_client_invoices(self, client_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        return self._repo.get_invoices(client_id, limit=limit)

    def get_client_revenue_history(self, client_id: int, months: int = 12) -> List[Dict[str, Any]]:
        return self._repo.get_revenue_history(client_id, months=months)

    def get_outstanding_invoices(self, client_id: int) -> List[Dict[str, Any]]:
        return self._inv_repo.get_outstanding_by_client(client_id)

    def get_outstanding_balance(self, client_id: int) -> float:
        return self._inv_repo.get_outstanding_balance(client_id)

    # ── Contact management ──────────────────────────────────────────────

    def get_contacts(self, client_id: int) -> List[Dict[str, Any]]:
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

    def get_tags(self, client_id: int) -> List[str]:
        rows = self._tag_repo.get_by_client(client_id)
        return [r["tag"] for r in rows]

    def add_tag(self, client_id: int, tag: str) -> None:
        self._tag_repo.add(client_id, tag)

    def remove_tag(self, client_id: int, tag: str) -> None:
        self._tag_repo.remove(client_id, tag)

    def get_all_tags(self) -> List[str]:
        return self._tag_repo.get_all_tags()

    # ── Payment tracking ────────────────────────────────────────────────

    def get_payment_summary(self, client_id: int) -> Dict[str, Any]:
        invs = self._inv_repo.get_by_client_id(client_id, limit=500)
        total_billed = sum(i.get("total_amount", 0) or 0 for i in invs)
        total_paid = sum(i.get("total_amount", 0) or 0 for i in invs if i.get("status") == "Paid")
        unpaid = sum(i.get("total_amount", 0) or 0 for i in invs if i.get("status") == "Unpaid")
        from datetime import datetime
        today = datetime.utcnow().strftime("%Y-%m-%d")
        overdue = sum(
            i.get("total_amount", 0) or 0
            for i in invs
            if i.get("status") == "Unpaid" and i.get("due_date", "") < today
        )
        return {
            "total_billed": total_billed,
            "total_paid": total_paid,
            "unpaid": unpaid,
            "overdue": overdue,
            "invoice_count": len(invs),
        }

    # ── Merge ───────────────────────────────────────────────────────────

    def merge_clients(self, from_id: int, to_id: int) -> Dict[str, int]:
        moved_trips = 0
        moved_invoices = 0
        moved_contacts = 0

        trips = self._repo.get_trips(from_id, limit=10000)
        for t in trips:
            self.db.conn.execute("UPDATE trips SET client_id = ? WHERE id = ?", (to_id, t["id"]))
            moved_trips += 1

        invs = self._repo.get_invoices(from_id, limit=10000)
        for inv in invs:
            tid = inv.get("trip_id")
            if tid:
                existing = self._inv_repo.get_by_trip_id(tid)
                if not existing:
                    self.db.conn.execute("UPDATE invoices SET trip_id = ? WHERE id = ?", (tid, inv.get("id")))
                moved_invoices += 1

        contacts = self._contact_repo.get_by_client(from_id)
        for c in contacts:
            self._contact_repo.update(c["id"], {"client_id": to_id})
            moved_contacts += 1

        self.db.conn.execute("UPDATE client_tags SET client_id = ? WHERE client_id = ?", (to_id, from_id))
        self.deactivate(from_id)
        self.db.conn.commit()

        self._event_bus.publish(CLIENT_MERGED, {"from_id": from_id, "to_id": to_id, "trips": moved_trips})
        return {"trips": moved_trips, "invoices": moved_invoices, "contacts": moved_contacts}

    # ── Export ──────────────────────────────────────────────────────────

    def export_clients_csv(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._repo.get_all_with_revenue(include_inactive=include_inactive)

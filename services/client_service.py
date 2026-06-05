"""Client service — business logic for client management."""
from typing import Any, Dict, List, Optional

from repositories.client_repository import ClientRepository
from repositories.invoice_repository import InvoiceRepository
from services.operations.event_bus import EventBus


class ClientService:
    def __init__(self, db):
        self._repo = ClientRepository(db)
        self._inv_repo = InvoiceRepository(db)
        self._event_bus = EventBus()

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
        """Return client_id for a given name, creating if not found."""
        name = name.strip()
        if not name:
            return None
        existing = self._repo.get_by_name(name)
        if existing:
            return existing["id"]
        return self.create(name=name)

    def resolve_client_id(self, name: str) -> Optional[int]:
        """Look up client_id by name. Returns None if not found."""
        name = name.strip()
        if not name:
            return None
        existing = self._repo.get_by_name(name)
        return existing["id"] if existing else None

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

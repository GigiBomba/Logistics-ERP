"""Client service — business logic for client management."""
from typing import Any, Dict, List, Optional

from repositories.client_repository import ClientRepository
from services.operations.event_bus import EventBus


class ClientService:
    def __init__(self, db):
        self._repo = ClientRepository(db)
        self._event_bus = EventBus()

    def get_by_id(self, client_id: int) -> Optional[Dict[str, Any]]:
        return self._repo.get_by_id(client_id)

    def get_all(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        return self._repo.get_all(include_inactive=include_inactive)

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        return self._repo.search(query, limit=limit)

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

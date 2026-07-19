"""Payment profile service — business logic for custom payment profiles."""
import logging
from typing import Any, Dict, List, Optional

from database.db_manager import DatabaseManager
from repositories.payment_profile_repository import PaymentProfileRepository

logger = logging.getLogger(__name__)


class PaymentProfileService:
    def __init__(self, db: DatabaseManager):
        self._repo = PaymentProfileRepository(db)

    def get_all(self, include_inactive: bool = False, limit: int = 500, company_id=None) -> List[Dict[str, Any]]:
        return self._repo.get_all(include_inactive=include_inactive, limit=limit)

    def get_by_id(self, profile_id: int, company_id=None) -> Optional[Dict[str, Any]]:
        return self._repo.get_by_id(profile_id)

    def search(self, query: str, limit: int = 20, company_id=None) -> List[Dict[str, Any]]:
        return self._repo.search(query, limit=limit)

    def get_active_by_type(self, recipient_type: str, limit: int = 500) -> List[Dict[str, Any]]:
        return self._repo.get_active_by_type(recipient_type, limit=limit)

    def create(self, data: Dict[str, Any], company_id=None) -> int:
        return self._repo.create(data)

    def update(self, profile_id: int, data: Dict[str, Any], company_id=None) -> None:
        self._repo.update(profile_id, data)

    def delete(self, profile_id: int, company_id=None) -> None:
        self._repo.delete(profile_id)

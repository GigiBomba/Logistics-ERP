import contextvars
from typing import AsyncGenerator, Optional

from fastapi import Depends

from config import Config
from database.db_manager import DatabaseManager
from repositories.document_repository import DocumentRepository
from repositories.driver_repository import DriverRepository
from repositories.trip_repository import TripRepository
from services.analytics_service import AnalyticsService
from services.client_service import ClientService
from services.document_service import DocumentService
from services.fleet_service import FleetService
from services.trip_service import TripService

# Request-scoped context for multi-tenant isolation.
_current_company_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("company_id", default=None)
_current_user_role: contextvars.ContextVar[str] = contextvars.ContextVar("user_role", default="")


def set_request_user_context(company_id: Optional[int], role: str) -> None:
    """Set the current request's user context (company_id, role).

    Called from ``get_current_user`` in the security middleware.
    """
    _current_company_id.set(company_id)
    _current_user_role.set(role)


def get_request_company_id() -> Optional[int]:
    return _current_company_id.get()


def get_request_user_role() -> str:
    return _current_user_role.get()


async def get_db() -> AsyncGenerator[DatabaseManager, None]:
    db = DatabaseManager(Config.DB_PATH)
    db.user_company_id = get_request_company_id()
    db.user_role = get_request_user_role()
    try:
        yield db
    finally:
        db.close()


async def get_document_repo(
    db: DatabaseManager = Depends(get_db),
) -> DocumentRepository:
    return DocumentRepository(db)


async def get_document_service(
    db: DatabaseManager = Depends(get_db),
) -> DocumentService:
    return DocumentService(db)


async def get_trip_repo(
    db: DatabaseManager = Depends(get_db),
) -> TripRepository:
    return TripRepository(db)


async def get_trip_service(
    db: DatabaseManager = Depends(get_db),
) -> TripService:
    return TripService(db)


async def get_client_service(
    db: DatabaseManager = Depends(get_db),
) -> ClientService:
    return ClientService(db)


async def get_fleet_service(
    db: DatabaseManager = Depends(get_db),
) -> FleetService:
    return FleetService(db)


async def get_driver_repo(
    db: DatabaseManager = Depends(get_db),
) -> DriverRepository:
    return DriverRepository(db)


async def get_analytics_service(
    db: DatabaseManager = Depends(get_db),
) -> AnalyticsService:
    return AnalyticsService(db)

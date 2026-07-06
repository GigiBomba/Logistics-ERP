from typing import AsyncGenerator

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

async def get_db() -> AsyncGenerator[DatabaseManager, None]:
    db = DatabaseManager(Config.DB_PATH)
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

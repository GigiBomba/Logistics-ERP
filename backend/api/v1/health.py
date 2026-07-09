import logging
from typing import Dict

from fastapi import APIRouter, Depends

from backend.dependencies import get_db
from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check(db: DatabaseManager = Depends(get_db)) -> Dict[str, str]:
    db_ok = False
    try:
        db.conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception as exc:
        logger.warning("Health check DB ping failed: %s", exc)
    return {
        "status": "ok",
        "version": "1.0.0",
        "database": "connected" if db_ok else "disconnected",
    }

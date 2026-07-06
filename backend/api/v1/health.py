from typing import Dict

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "version": "1.0.0", "database": "operion"}

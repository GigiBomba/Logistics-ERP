"""Health check endpoints — liveness, readiness, and detailed health."""
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def health_check(db: DatabaseManager = Depends(get_db)) -> Dict[str, Any]:
    """Legacy health check — returns basic status with DB connectivity.

    This is a combined liveness + readiness check. For separate probes, use:
    - GET /health/live — liveness  (is the process running?)
    - GET /health/ready — readiness (can it serve traffic?)
    """
    db_ok = False
    pool_stats = None
    try:
        db.execute("SELECT 1").fetchone()
        db_ok = True
        pool_stats = db.health_stats
    except Exception as exc:
        logger.warning("Health check DB ping failed: %s", exc)
    return {
        "status": "ok",
        "version": "1.0.0",
        "database": "connected" if db_ok else "disconnected",
        "pool": pool_stats,
        "timestamp": time.time(),
    }


@router.get("/live")
async def liveness_probe() -> Dict[str, Any]:
    """Kubernetes liveness probe.

    Returns 200 if the application process is alive.
    Lightweight — no DB checks, no external calls.
    If this fails, the container will be restarted.
    """
    return {"status": "alive", "timestamp": time.time()}


@router.get("/ready")
async def readiness_probe(db: DatabaseManager = Depends(get_db)):
    """Kubernetes readiness probe.

    Returns 200 if the application is ready to serve traffic.
    Checks:
    - Database connectivity
    - Redis connectivity (if configured)
    - Celery worker availability (if configured)

    If this fails, traffic will be routed away from this pod.
    """
    checks: Dict[str, str] = {}
    ready = True

    # 1. Database connectivity
    try:
        db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
        ready = False

    # 2. Redis connectivity (non-critical)
    try:
        from backend.cache import get_cache
        cache = get_cache()
        if cache:
            cache._redis.ping()
            checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"unavailable: {e}"

    # 3. Celery worker check (non-critical)
    try:
        from backend.celery_app.celery import celery_app
        insp = celery_app.control.inspect(timeout=2)
        stats = insp.stats() if insp else None
        if stats:
            checks["celery"] = f"ok ({len(stats)} workers)"
        else:
            checks["celery"] = "no workers available"
    except Exception as e:
        checks["celery"] = f"unavailable: {e}"

    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if ready else "not_ready",
            "checks": checks,
            "timestamp": time.time(),
        },
    )

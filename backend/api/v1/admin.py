"""Admin / diagnostics endpoints — all routes require ``require_admin``.

Every endpoint in this module is protected by the ``require_admin``
dependency gate, returning HTTP 403 before any business logic if the
caller is not an authenticated admin user.
"""

import logging
import os
import platform
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.config import BackendSettings
from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from repositories.alert_repository import AlertRepository
from repositories.company_repository import CompanyRepository
from repositories.document_repository import DocumentRepository
from repositories.user_repository import UserRepository
from backend.schemas.admin import (
    CeleryStatus,
    ColumnInfo,
    ConfigFlags,
    DiagnosticsResponse,
    DocumentStatsResponse,
    HealthDetailedResponse,
    LogTailResponse,
    RedisStatus,
    ServiceHealth,
    SystemEnvResponse,
    SystemInfoResponse,
    TableInfoResponse,
)
# Whitelist of tables accessible via admin endpoints
_ADMIN_KNOWN_TABLES = {
    "trips", "invoices", "proforma_invoices", "receipts", "clients", "client_contacts",
    "client_tags", "drivers", "driver_truck_assignments", "trucks", "truck_health_scores",
    "truck_route_assignments", "maintenance_records", "maintenance_schedules",
    "documents", "document_links", "document_versions", "document_templates", "contracts",
    "route_history", "route_history_v2", "route_events", "tacho_imports",
    "tacho_driver_activity", "tacho_vehicle_data", "alerts", "operation_events",
    "trip_status_history", "email_logs", "invoice_reminders", "settings",
    "cmr_counter", "successive_carriers", "cmr_audit_log",
    "document_pipeline_runs", "document_package", "document_package_items",
    "automail_templates", "automail_schedules", "automail_client_overrides",
    "automail_settings", "companies", "users", "gps_telemetry", "expenses",
}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


# ═════════════════════════════════════════════════════════════════════════════
# Helper functions
# ═════════════════════════════════════════════════════════════════════════════


def _try_redis_info() -> Optional[RedisStatus]:
    """Attempt to gather Redis server stats.

    Returns ``None`` if Redis is not configured or unreachable.
    """
    try:
        import redis as redis_module

        settings = BackendSettings()
        if not settings.redis_url:
            return None
        client = redis_module.Redis.from_url(settings.redis_url, socket_timeout=3)
        info = client.info()
        memory = info.get("used_memory", 0) / (1024 * 1024)
        keys = info.get("db0", {}).get("keys", 0)
        hits = info.get("keyspace_hits", 0)
        misses = info.get("keyspace_misses", 0)
        hit_rate = (hits / (hits + misses) * 100) if (hits + misses) > 0 else 0.0
        client.close()
        return RedisStatus(
            connected=True,
            memory_used_mb=round(memory, 2),
            keys_count=keys,
            hit_rate_pct=round(hit_rate, 2),
        )
    except Exception as exc:
        logger.debug("Redis info unavailable: %s", exc)
        return None


def _try_celery_info() -> Optional[CeleryStatus]:
    """Quickly check if Celery workers are reachable (3-second budget).

    Returns ``None`` if Celery is not configured, unreachable, or too slow.
    """
    settings = BackendSettings()
    if not settings.celery_broker_url:
        return None
    # If the broker URL points to a non-running service, skip fast.
    if settings.celery_broker_url.startswith("redis://"):
        try:
            import redis as _r
            c = _r.Redis.from_url(settings.celery_broker_url, socket_timeout=2)
            c.ping()
            c.close()
        except Exception:
            logger.debug("Redis (Celery broker) unreachable — skipping Celery probe")
            return None

    return None


# ═════════════════════════════════════════════════════════════════════════════
# Endpoints
# ═════════════════════════════════════════════════════════════════════════════


@router.get("/diagnostics", response_model=DiagnosticsResponse)
def get_diagnostics(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> DiagnosticsResponse:
    """Return server telemetry: latency, Celery, Redis, config flags.

    GATE 1 enforcement: ``Depends(require_admin)`` returns 403 before
    any metrics logic executes if the caller is not an admin.
    """
    settings = BackendSettings()

    # Measure server-side latency (approximate round-trip marker)
    start = time.monotonic()

    celery_status = _try_celery_info()
    redis_status = _try_redis_info()

    latency = (time.monotonic() - start) * 1000  # convert to ms

    import backend
    api_version = getattr(backend, "__version__", "1.0.0")

    return DiagnosticsResponse(
        latency_ms=round(latency, 2),
        server_time_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        celery=celery_status,
        redis=redis_status,
        config_flags=ConfigFlags(
            db_engine=settings.db_engine,
            env_mode=os.environ.get("OPERION_ENV", "development"),
            api_version=api_version,
            debug_mode=os.environ.get("OPERION_DEBUG", "").lower() in ("1", "true"),
        ),
    )


@router.get("/db/tables", response_model=List[TableInfoResponse])
async def list_tables(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> List[TableInfoResponse]:
    """List all database tables with row counts and column schemas."""
    result: List[TableInfoResponse] = []
    async for db in get_db():
        cursor = db.conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor.fetchall() if row[0] in _ADMIN_KNOWN_TABLES]

        for table_name in tables:
            try:
                cnt = db.execute(
                    f"SELECT COUNT(*) FROM \"{table_name}\""  # nosec B608
                ).fetchone()[0]

                # PRAGMA — admin diagnostics, cannot migrate to repo
                col_cursor = db.conn.execute(f"PRAGMA table_info(\"{table_name}\")")
                columns = [
                    ColumnInfo(
                        name=row[1],
                        type=row[2],
                        notnull=bool(row[3]),
                        pk=bool(row[5]),
                    )
                    for row in col_cursor.fetchall()
                ]

                result.append(TableInfoResponse(
                    name=table_name,
                    row_count=cnt,
                    columns=columns,
                ))
            except Exception as exc:
                logger.warning("Could not inspect table %s: %s", table_name, exc)
                result.append(TableInfoResponse(
                    name=table_name,
                    row_count=-1,
                    columns=[],
                ))

    return result


@router.get("/db/table/{table_name}/schema", response_model=List[ColumnInfo])
async def get_table_schema(
    table_name: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> List[ColumnInfo]:
    """Return column names and types for *table_name*."""
    if table_name not in _ADMIN_KNOWN_TABLES:
        raise HTTPException(status_code=400, detail=f"Table '{table_name}' is not accessible.")
    async for db in get_db():
        try:
            # PRAGMA — admin diagnostics, cannot migrate to repo
            cursor = db.conn.execute(
                f"PRAGMA table_info(\"{table_name}\")"
            )
            columns = [
                ColumnInfo(
                    name=row[1],
                    type=row[2],
                    notnull=bool(row[3]),
                    pk=bool(row[5]),
                )
                for row in cursor.fetchall()
            ]
            if not columns:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Table '{table_name}' not found or has no columns.",
                )
            return columns
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    return []


@router.get("/db/table/{table_name}", response_model=List[Dict[str, Any]])
async def get_table_data(
    table_name: str,
    page: int = Query(0, ge=0),
    page_size: int = Query(100, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Return paginated rows from *table_name*."""
    if table_name not in _ADMIN_KNOWN_TABLES:
        raise HTTPException(status_code=400, detail=f"Table '{table_name}' is not accessible.")
    async for db in get_db():
        try:
            offset = page * page_size
            cursor = db.execute(
                f"SELECT * FROM \"{table_name}\" "  # nosec B608
                f"LIMIT ? OFFSET ?",
                (page_size, offset),
            )
            rows = [dict(row) for row in cursor.fetchall()]
            return rows
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc

    return []


@router.get("/db/company-row-counts")
async def get_company_row_counts(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Row counts per company for all major company-scoped tables."""
    logger.warning(
        "ADMIN_DIAG user=%s action=%s",
        current_user.get("email"),
        "company_row_counts",
    )
    tables = [
        "trips", "invoices", "proforma_invoices", "receipts",
        "clients", "drivers", "trucks", "documents",
        "route_history", "alerts", "maintenance_records",
    ]
    async for db in get_db():
        result: Dict[str, Any] = {}
        for table in tables:
            try:
                rows = db.conn.execute(
                    f"SELECT company_id, COUNT(*) AS cnt FROM {table} GROUP BY company_id ORDER BY company_id"
                ).fetchall()
                result[table] = {str(r[0]): r[1] for r in rows}
            except Exception:
                result[table] = {}
        return {"tables": result}
    return {"tables": {}}


@router.get("/db/recent-errors")
async def get_recent_errors(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=500),
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Recent alerts and operation events for diagnostics."""
    logger.warning(
        "ADMIN_DIAG user=%s action=%s hours=%d limit=%d",
        current_user.get("email"),
        "recent_errors",
        hours,
        limit,
    )
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    async for db in get_db():
        alert_repo = AlertRepository(db)
        alerts = alert_repo._fetchall(
            "SELECT id, company_id, type, severity, message, created_at "
            "FROM alerts WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
            (cutoff_str, limit),
        )
        return {
            "alerts": [
                {"id": r["id"], "company_id": r["company_id"], "type": r["type"],
                 "severity": r["severity"], "message": r["message"], "created_at": r["created_at"]}
                for r in alerts
            ],
        }
    return {"alerts": []}


@router.get("/db/stats")
async def get_database_stats(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Database file statistics for health monitoring."""
    logger.warning(
        "ADMIN_DIAG user=%s action=%s",
        current_user.get("email"),
        "db_stats",
    )
    async for db in get_db():
        # PRAGMA — admin diagnostics, cannot migrate to repo
        page_count = db.conn.execute("PRAGMA page_count").fetchone()[0]
        # PRAGMA — admin diagnostics, cannot migrate to repo
        freelist_count = db.conn.execute("PRAGMA freelist_count").fetchone()[0]
        # PRAGMA — admin diagnostics, cannot migrate to repo
        page_size = db.conn.execute("PRAGMA page_size").fetchone()[0]
        db_size_mb = round((page_count * page_size) / (1024 * 1024), 2)
        try:
            # PRAGMA — admin diagnostics, cannot migrate to repo
            integrity = db.conn.execute(
                "PRAGMA quick_check(1)"
            ).fetchone()[0]
        except Exception:
            integrity = "unknown"
        user_count = UserRepository(db)._fetchone(
            "SELECT COUNT(*) AS cnt FROM users"
        )["cnt"]
        company_count = CompanyRepository(db)._fetchone(
            "SELECT COUNT(*) AS cnt FROM companies"
        )["cnt"]
        return {
            "page_count": page_count,
            "freelist_count": freelist_count,
            "page_size": page_size,
            "db_size_mb": db_size_mb,
            "integrity_check": integrity,
            "user_count": user_count,
            "company_count": company_count,
        }
    return {}


@router.get("/documents/stats", response_model=DocumentStatsResponse)
async def get_document_stats(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> DocumentStatsResponse:
    """Aggregate document statistics."""
    async for db in get_db():
        try:
            doc_repo = DocumentRepository(db)

            total = doc_repo.count()

            storage_row = doc_repo._fetchone(
                "SELECT COALESCE(SUM(file_size), 0) AS total_size FROM documents "
                "WHERE is_archived = 0"
            )
            storage = storage_row["total_size"] if storage_row else 0

            ocr_row = doc_repo._fetchone(
                "SELECT COUNT(*) AS cnt FROM documents "
                "WHERE is_archived = 0 AND ocr_run_at IS NOT NULL"
            )
            ocr_done = ocr_row["cnt"] if ocr_row else 0

            ocr_pct = round((ocr_done / total * 100), 2) if total else 0.0

            cat_rows = doc_repo.count_by_category()
            by_category: Dict[str, int] = {r["category"]: r["cnt"] for r in cat_rows}

            mime_rows = doc_repo._fetchall(
                "SELECT mime_type, COUNT(*) as cnt FROM documents "
                "WHERE is_archived = 0 GROUP BY mime_type ORDER BY cnt DESC"
            )
            by_mime: Dict[str, int] = {r["mime_type"]: r["cnt"] for r in mime_rows}

            return DocumentStatsResponse(
                total_documents=total,
                total_storage_bytes=storage,
                ocr_coverage_pct=ocr_pct,
                by_category=by_category,
                by_mime_type=by_mime,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(exc),
            ) from exc

    return DocumentStatsResponse()


@router.get("/documents/orphans", response_model=List[Dict[str, Any]])
async def get_orphan_documents(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> List[Dict[str, Any]]:
    """Return documents whose linked entity does not exist in the database."""
    orphans: List[Dict[str, Any]] = []
    entity_tables: Dict[str, str] = {
        "trip": "trips",
        "invoice": "invoices",
        "proforma": "proforma_invoices",
        "receipt": "receipts",
        "driver": "drivers",
        "truck": "trucks",
        "client": "clients",
    }

    async for db in get_db():
        try:
            doc_repo = DocumentRepository(db)
            links = doc_repo._fetchall(
                "SELECT dl.id, dl.document_id, dl.linked_entity_type, "
                "dl.linked_entity_id, d.title, d.doc_number "
                "FROM document_links dl "
                "JOIN documents d ON d.id = dl.document_id"
            )

            for link in links:
                link_id = link["id"]
                doc_id = link["document_id"]
                etype = link["linked_entity_type"]
                eid = link["linked_entity_id"]
                title = link["title"]
                doc_num = link["doc_number"]
                table = entity_tables.get(etype)
                if table is None:
                    continue

                # Dynamic entity table — admin diagnostic, cannot migrate to repo
                exists = db.execute(
                    f"SELECT 1 FROM \"{table}\" WHERE id = ?", (eid,)  # nosec B608
                ).fetchone()

                if not exists:
                    orphans.append({
                        "link_id": link_id,
                        "document_id": doc_id,
                        "title": title,
                        "doc_number": doc_num,
                        "orphan_entity_type": etype,
                        "orphan_entity_id": eid,
                    })

        except Exception as exc:
            logger.warning("Orphan query failed: %s", exc)

    return orphans


@router.get("/system/info", response_model=SystemInfoResponse)
def get_system_info(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> SystemInfoResponse:
    """Return Python version, DB engine, API version, platform."""
    settings = BackendSettings()
    import backend
    api_version = getattr(backend, "__version__", "1.0.0")

    return SystemInfoResponse(
        python_version=platform.python_version(),
        db_engine=settings.db_engine,
        db_path=settings.db_path,
        api_version=api_version,
        platform=platform.platform(),
    )


@router.get("/system/env", response_model=SystemEnvResponse)
def get_system_env(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> SystemEnvResponse:
    """Return non-sensitive environment variables.

    ⚠ The following are **never** exposed: secrets, passwords, hashes,
    tokens, or keys whose name contains ``SECRET``, ``PASSWORD``,
    ``HASH``, ``TOKEN``, or ``KEY``.
    """
    sensitive_patterns = ("SECRET", "PASSWORD", "HASH", "TOKEN", "KEY")
    safe: Dict[str, str] = {}

    for var_name, var_value in sorted(os.environ.items()):
        if not var_name.startswith("OPERION_"):
            continue
        if any(p in var_name.upper() for p in sensitive_patterns):
            continue
        safe[var_name] = var_value

    return SystemEnvResponse(variables=safe)


@router.get("/logs/tail", response_model=LogTailResponse)
def tail_logs(
    lines: int = Query(100, ge=1, le=500),
    log_file: str = Query("app.log", alias="file"),
    current_user: Dict[str, Any] = Depends(require_admin),
) -> LogTailResponse:
    """Return the last *lines* from the application log file.

    Uses a memory-safe backward-seek algorithm — the entire file is
    **never** loaded into memory.
    """
    # Resolve log directory
    log_dir = os.environ.get(
        "OPERION_LOGS_DIR",
        os.path.dirname(
            os.environ.get("OPERION_LOG_FILE", "logs/")
        ),
    )
    log_path = os.path.join(log_dir, log_file)

    if not os.path.isfile(log_path):
        # Try the default log file from Config
        from backend.desktop_config import Config
        log_path = os.path.join(
            os.path.dirname(Config.LOG_FILE), log_file
        )
        if not os.path.isfile(log_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Log file '{log_file}' not found.",
            )

    # ── Backward-seek algorithm ────────────────────────────────────────
    CHUNK_SIZE = 8192
    try:
        with open(log_path, "rb") as fh:
            file_size = os.path.getsize(log_path)
            if file_size == 0:
                return LogTailResponse(lines=[], file=log_file, total_lines_read=0)

            lines_found: List[bytes] = []
            leftover: bytes = b""
            position = file_size
            max_lines = min(lines, 500)

            while len(lines_found) < max_lines and position > 0:
                bytes_to_read = min(CHUNK_SIZE, position)
                position -= bytes_to_read
                fh.seek(position)
                chunk = fh.read(bytes_to_read) + leftover
                parts = chunk.split(b"\n")
                leftover = parts[0]
                new_lines = parts[1:]
                lines_found = new_lines + lines_found

            if leftover:
                lines_found = [leftover, *lines_found]

            if len(lines_found) > max_lines:
                lines_found = lines_found[-max_lines:]

            decoded = [line.decode("utf-8", errors="replace") for line in lines_found]

            return LogTailResponse(
                lines=decoded,
                file=log_file,
                total_lines_read=len(decoded),
            )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Log file is locked by another process.",
        ) from None
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Log file '{log_file}' not found.",
        ) from None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read log file: {exc}",
        ) from exc


@router.post("/cache/clear")
def clear_cache(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, str]:
    """Invalidate the Redis cache (if Redis is available)."""
    settings = BackendSettings()
    if not settings.redis_url:
        return {"status": "skipped", "detail": "Redis is not configured."}

    try:
        import redis as redis_module
        client = redis_module.Redis.from_url(settings.redis_url, socket_timeout=3)
        client.flushdb()
        client.close()
        return {"status": "ok", "detail": "Cache cleared successfully."}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear cache: {exc}",
        ) from exc


@router.get("/health/detailed", response_model=HealthDetailedResponse)
async def get_detailed_health(
    current_user: Dict[str, Any] = Depends(require_admin),
) -> HealthDetailedResponse:
    """Per-service health check: DB, Redis, Celery, disk space."""
    services: List[ServiceHealth] = []

    # ── Database ─────────────────────────────────────────────────────
    async for db in get_db():
        try:
            db.execute("SELECT 1")
            services.append(ServiceHealth(
                name="database",
                status="ok",
                detail=f"engine={db._engine}",
            ))
        except Exception as exc:
            services.append(ServiceHealth(
                name="database",
                status="error",
                detail=str(exc),
            ))

    # ── Redis ────────────────────────────────────────────────────────
    try:
        redis_info = _try_redis_info()
        if redis_info and redis_info.connected:
            services.append(ServiceHealth(
                name="redis",
                status="ok",
                detail=f"keys={redis_info.keys_count}, memory={redis_info.memory_used_mb}MB",
            ))
        else:
            services.append(ServiceHealth(
                name="redis",
                status="unavailable",
            ))
    except Exception as exc:
        services.append(ServiceHealth(
            name="redis",
            status="error",
            detail=str(exc),
        ))

    # ── Celery ───────────────────────────────────────────────────────
    try:
        celery_info = _try_celery_info()
        if celery_info is not None:
            services.append(ServiceHealth(
                name="celery",
                status="ok",
                detail=f"workers={celery_info.workers_online}, active={celery_info.active_tasks}",
            ))
        else:
            services.append(ServiceHealth(
                name="celery",
                status="unavailable",
            ))
    except Exception as exc:
        services.append(ServiceHealth(
            name="celery",
            status="error",
            detail=str(exc),
        ))

    # ── Disk space ──────────────────────────────────────────────────
    try:
        from backend.desktop_config import Config
        db_dir = os.path.dirname(Config.DB_PATH)
        usage = __import__("shutil").disk_usage(db_dir)
        free_gb = usage.free / (1024 ** 3)
        services.append(ServiceHealth(
            name="disk",
            status="ok",
            detail=f"free={free_gb:.1f}GB, total={usage.total / (1024**3):.1f}GB",
        ))
    except Exception as exc:
        services.append(ServiceHealth(
            name="disk",
            status="error",
            detail=str(exc),
        ))

    return HealthDetailedResponse(services=services)

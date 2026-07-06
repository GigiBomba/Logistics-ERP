"""Pydantic models for admin / diagnostics endpoints."""

from typing import Dict, List, Optional

from pydantic import BaseModel

# ── Multi-tenant ─────────────────────────────────────────────────────────────


class CompanyInfo(BaseModel):
    id: int = 0
    name: str = ""
    subscription_tier: str = "starter"
    is_active: bool = True


# ── Diagnostics ──────────────────────────────────────────────────────────────


class CeleryStatus(BaseModel):
    active_tasks: int = 0
    scheduled_tasks: int = 0
    queue_size: int = 0
    workers_online: int = 0


class RedisStatus(BaseModel):
    connected: bool = False
    memory_used_mb: Optional[float] = None
    keys_count: Optional[int] = None
    hit_rate_pct: Optional[float] = None


class ConfigFlags(BaseModel):
    db_engine: str = ""
    env_mode: str = ""
    api_version: str = ""
    debug_mode: bool = False


class DiagnosticsResponse(BaseModel):
    latency_ms: float = 0.0
    server_time_utc: str = ""
    celery: Optional[CeleryStatus] = None
    redis: Optional[RedisStatus] = None
    config_flags: ConfigFlags


# ── Database inspector ───────────────────────────────────────────────────────


class ColumnInfo(BaseModel):
    name: str
    type: str
    notnull: bool = False
    pk: bool = False


class TableInfoResponse(BaseModel):
    name: str
    row_count: int
    columns: List[ColumnInfo]


class RawQueryRequest(BaseModel):
    query: str
    limit: int = 100


# ── Document stats ───────────────────────────────────────────────────────────


class DocumentStatsResponse(BaseModel):
    total_documents: int = 0
    total_storage_bytes: int = 0
    ocr_coverage_pct: float = 0.0
    by_category: Dict[str, int] = {}
    by_mime_type: Dict[str, int] = {}


# ── System info ──────────────────────────────────────────────────────────────


class SystemInfoResponse(BaseModel):
    python_version: str = ""
    db_engine: str = ""
    db_path: str = ""
    api_version: str = ""
    platform: str = ""


class SystemEnvResponse(BaseModel):
    variables: Dict[str, str] = {}


# ── Log tail ─────────────────────────────────────────────────────────────────


class LogTailResponse(BaseModel):
    lines: List[str] = []
    file: str = ""
    total_lines_read: int = 0


# ── Health ────────────────────────────────────────────────────────────────────


class ServiceHealth(BaseModel):
    name: str
    status: str  # "ok", "error", "unavailable"
    detail: Optional[str] = None


class HealthDetailedResponse(BaseModel):
    services: List[ServiceHealth] = []

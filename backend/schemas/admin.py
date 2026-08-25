"""Pydantic models for admin / diagnostics endpoints."""
from __future__ import annotations


from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict

# ── Multi-tenant ─────────────────────────────────────────────────────────────


class CompanyInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = 0
    name: str = ""
    subscription_tier: str = "starter"
    is_active: bool = True


# ── Diagnostics ──────────────────────────────────────────────────────────────


class CeleryStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active_tasks: int = 0
    scheduled_tasks: int = 0
    queue_size: int = 0
    workers_online: int = 0


class RedisStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connected: bool = False
    memory_used_mb: Optional[float] = None
    keys_count: Optional[int] = None
    hit_rate_pct: Optional[float] = None


class ConfigFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    db_engine: str = ""
    env_mode: str = ""
    api_version: str = ""
    debug_mode: bool = False


class DiagnosticsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latency_ms: float = 0.0
    server_time_utc: str = ""
    celery: Optional[CeleryStatus] = None
    redis: Optional[RedisStatus] = None
    config_flags: ConfigFlags


# ── Database inspector ───────────────────────────────────────────────────────


class ColumnInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: str
    notnull: bool = False
    pk: bool = False


class TableInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    row_count: int
    columns: List[ColumnInfo]


# ── Document stats ───────────────────────────────────────────────────────────


class DocumentStatsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_documents: int = 0
    total_storage_bytes: int = 0
    ocr_coverage_pct: float = 0.0
    by_category: Dict[str, int] = {}
    by_mime_type: Dict[str, int] = {}


# ── System info ──────────────────────────────────────────────────────────────


class SystemInfoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    python_version: str = ""
    db_engine: str = ""
    db_path: str = ""
    api_version: str = ""
    platform: str = ""


class SystemEnvResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variables: Dict[str, str] = {}


# ── Log tail ─────────────────────────────────────────────────────────────────


class LogTailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lines: List[str] = []
    file: str = ""
    total_lines_read: int = 0


# ── Health ────────────────────────────────────────────────────────────────────


class ServiceHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str  # "ok", "error", "unavailable"
    detail: Optional[str] = None


class HealthDetailedResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    services: List[ServiceHealth] = []

"""Tests for backend/schemas/admin.py — admin, diagnostics, health schemas."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest
from pydantic import ValidationError

from backend.schemas.admin import (
    CeleryStatus,
    ColumnInfo,
    CompanyInfo,
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


# ── Helpers ───────────────────────────────────────────────────────────────────


def assert_extra_forbidden(model_cls: type, valid_kwargs: Dict[str, Any]) -> None:
    """Assert that passing an unknown field raises ValidationError."""
    with pytest.raises(ValidationError):
        model_cls(**valid_kwargs, _unknown_extra="x")  # type: ignore[call-arg]


# ── CompanyInfo ───────────────────────────────────────────────────────────────


class TestCompanyInfo:
    def test_defaults(self):
        inst = CompanyInfo()
        assert inst.id == 0
        assert inst.name == ""
        assert inst.subscription_tier == "starter"
        assert inst.is_active is True

    def test_custom_values(self):
        inst = CompanyInfo(id=1, name="Acme", subscription_tier="enterprise", is_active=False)
        assert inst.id == 1
        assert inst.name == "Acme"
        assert inst.subscription_tier == "enterprise"
        assert inst.is_active is False

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            CompanyInfo(name="Acme", extra="x")  # type: ignore[call-arg]


# ── CeleryStatus ──────────────────────────────────────────────────────────────


class TestCeleryStatus:
    def test_defaults(self):
        inst = CeleryStatus()
        assert inst.active_tasks == 0
        assert inst.scheduled_tasks == 0
        assert inst.queue_size == 0
        assert inst.workers_online == 0

    def test_custom_values(self):
        inst = CeleryStatus(active_tasks=3, scheduled_tasks=5, queue_size=2, workers_online=4)
        assert inst.active_tasks == 3
        assert inst.workers_online == 4

    def test_extra_field_forbidden(self):
        assert_extra_forbidden(CeleryStatus, {})


# ── RedisStatus ───────────────────────────────────────────────────────────────


class TestRedisStatus:
    def test_defaults(self):
        inst = RedisStatus()
        assert inst.connected is False
        assert inst.memory_used_mb is None
        assert inst.keys_count is None
        assert inst.hit_rate_pct is None

    def test_connected_with_metrics(self):
        inst = RedisStatus(connected=True, memory_used_mb=128.5, keys_count=42, hit_rate_pct=99.1)
        assert inst.connected is True
        assert inst.memory_used_mb == 128.5
        assert inst.keys_count == 42
        assert inst.hit_rate_pct == 99.1

    def test_extra_field_forbidden(self):
        assert_extra_forbidden(RedisStatus, {})


# ── ConfigFlags ───────────────────────────────────────────────────────────────


class TestConfigFlags:
    def test_defaults(self):
        inst = ConfigFlags()
        assert inst.db_engine == ""
        assert inst.env_mode == ""
        assert inst.api_version == ""
        assert inst.debug_mode is False

    def test_all_fields(self):
        inst = ConfigFlags(db_engine="postgresql", env_mode="production", api_version="2.0", debug_mode=True)
        assert inst.db_engine == "postgresql"
        assert inst.debug_mode is True

    def test_extra_field_forbidden(self):
        assert_extra_forbidden(ConfigFlags, {})


# ── DiagnosticsResponse ───────────────────────────────────────────────────────


class TestDiagnosticsResponse:
    """Has a required config_flags: ConfigFlags field."""

    def test_minimal(self):
        """config_flags is required; others have defaults."""
        inst = DiagnosticsResponse(config_flags=ConfigFlags())
        assert inst.latency_ms == 0.0
        assert inst.server_time_utc == ""
        assert inst.celery is None
        assert inst.redis is None
        assert inst.config_flags.db_engine == ""

    def test_all_nested(self):
        config = ConfigFlags(db_engine="sqlite", env_mode="test", api_version="1.0", debug_mode=True)
        celery = CeleryStatus(active_tasks=2)
        redis = RedisStatus(connected=True)
        inst = DiagnosticsResponse(
            latency_ms=12.5,
            server_time_utc="2025-01-01T00:00:00Z",
            celery=celery,
            redis=redis,
            config_flags=config,
        )
        assert inst.latency_ms == 12.5
        assert inst.celery.active_tasks == 2
        assert inst.redis.connected is True

    def test_missing_config_flags_raises(self):
        with pytest.raises(ValidationError):
            DiagnosticsResponse()  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DiagnosticsResponse(config_flags=ConfigFlags(), unknown="x")  # type: ignore[call-arg]


# ── ColumnInfo ────────────────────────────────────────────────────────────────


class TestColumnInfo:
    """name (required), type (required), notnull (default False), pk (default False)."""

    def test_required_only(self):
        inst = ColumnInfo(name="id", type="INTEGER")
        assert inst.name == "id"
        assert inst.type == "INTEGER"
        assert inst.notnull is False
        assert inst.pk is False

    def test_all_fields(self):
        inst = ColumnInfo(name="name", type="TEXT", notnull=True, pk=False)
        assert inst.notnull is True

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ColumnInfo(type="INTEGER")  # type: ignore[call-arg]

    def test_missing_type_raises(self):
        with pytest.raises(ValidationError):
            ColumnInfo(name="id")  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ColumnInfo(name="id", type="INT", default="0")  # type: ignore[call-arg]


# ── TableInfoResponse ─────────────────────────────────────────────────────────


class TestTableInfoResponse:
    def test_valid(self):
        cols = [ColumnInfo(name="id", type="INTEGER", pk=True)]
        inst = TableInfoResponse(name="users", row_count=100, columns=cols)
        assert inst.name == "users"
        assert inst.row_count == 100
        assert inst.columns == cols

    def test_empty_columns(self):
        inst = TableInfoResponse(name="empty", row_count=0, columns=[])
        assert inst.columns == []

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            TableInfoResponse(row_count=0, columns=[])  # type: ignore[call-arg]

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            TableInfoResponse(name="t", row_count=0, columns=[], bad=1)  # type: ignore[call-arg]


# ── DocumentStatsResponse ─────────────────────────────────────────────────────


class TestDocumentStatsResponse:
    def test_defaults(self):
        inst = DocumentStatsResponse()
        assert inst.total_documents == 0
        assert inst.total_storage_bytes == 0
        assert inst.ocr_coverage_pct == 0.0
        assert inst.by_category == {}
        assert inst.by_mime_type == {}

    def test_custom_values(self):
        inst = DocumentStatsResponse(
            total_documents=100,
            total_storage_bytes=1048576,
            ocr_coverage_pct=75.5,
            by_category={"invoice": 40, "contract": 60},
            by_mime_type={"application/pdf": 80, "image/png": 20},
        )
        assert inst.total_documents == 100
        assert inst.by_category["invoice"] == 40

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            DocumentStatsResponse(unknown=1)  # type: ignore[call-arg]


# ── SystemInfoResponse ────────────────────────────────────────────────────────


class TestSystemInfoResponse:
    def test_defaults(self):
        inst = SystemInfoResponse()
        assert inst.python_version == ""
        assert inst.db_engine == ""
        assert inst.db_path == ""
        assert inst.api_version == ""
        assert inst.platform == ""

    def test_all_fields(self):
        inst = SystemInfoResponse(
            python_version="3.12", db_engine="sqlite", db_path="/data/db.sqlite",
            api_version="1.5", platform="win32",
        )
        assert inst.python_version == "3.12"
        assert inst.platform == "win32"

    def test_extra_field_forbidden(self):
        assert_extra_forbidden(SystemInfoResponse, {})


# ── SystemEnvResponse ─────────────────────────────────────────────────────────


class TestSystemEnvResponse:
    def test_defaults(self):
        inst = SystemEnvResponse()
        assert inst.variables == {}

    def test_with_variables(self):
        inst = SystemEnvResponse(variables={"PATH": "/usr/bin", "HOME": "/root"})
        assert inst.variables["PATH"] == "/usr/bin"

    def test_extra_field_forbidden(self):
        assert_extra_forbidden(SystemEnvResponse, {})


# ── LogTailResponse ───────────────────────────────────────────────────────────


class TestLogTailResponse:
    def test_defaults(self):
        inst = LogTailResponse()
        assert inst.lines == []
        assert inst.file == ""
        assert inst.total_lines_read == 0

    def test_with_lines(self):
        inst = LogTailResponse(lines=["info: started", "warn: low memory"], file="/var/log/app.log", total_lines_read=2)
        assert len(inst.lines) == 2
        assert inst.file == "/var/log/app.log"
        assert inst.total_lines_read == 2

    def test_extra_field_forbidden(self):
        assert_extra_forbidden(LogTailResponse, {})


# ── ServiceHealth ─────────────────────────────────────────────────────────────


class TestServiceHealth:
    """name (required), status (required), detail: Optional[str] = None."""

    def test_required_only(self):
        inst = ServiceHealth(name="database", status="ok")
        assert inst.name == "database"
        assert inst.status == "ok"
        assert inst.detail is None

    def test_with_detail(self):
        inst = ServiceHealth(name="redis", status="error", detail="Connection refused")
        assert inst.detail == "Connection refused"

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError):
            ServiceHealth(status="ok")  # type: ignore[call-arg]

    def test_missing_status_raises(self):
        with pytest.raises(ValidationError):
            ServiceHealth(name="db")  # type: ignore[call-arg]

    @pytest.mark.parametrize("status_value", ["ok", "error", "unavailable", "unknown"])
    def test_any_status_string_allowed(self, status_value: str):
        """No enum constraint — any string is accepted."""
        inst = ServiceHealth(name="svc", status=status_value)
        assert inst.status == status_value

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            ServiceHealth(name="x", status="ok", extra="y")  # type: ignore[call-arg]


# ── HealthDetailedResponse ────────────────────────────────────────────────────


class TestHealthDetailedResponse:
    def test_defaults(self):
        inst = HealthDetailedResponse()
        assert inst.services == []

    def test_with_services(self):
        services = [
            ServiceHealth(name="db", status="ok"),
            ServiceHealth(name="cache", status="error", detail="timeout"),
        ]
        inst = HealthDetailedResponse(services=services)
        assert len(inst.services) == 2
        assert inst.services[1].detail == "timeout"

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            HealthDetailedResponse(metadata="x")  # type: ignore[call-arg]

"""ObservabilityPanel — dev-toolkit Co-Pilot observability widget (§23.6).

Shows the Co-Pilot runtime signals the backend actually produces today:
confidence distribution, tool failure rate, abandonment rate, circuit-breaker
trips, per-phase timings, and LLM provider health.

Data sources (all read-only, all guarded so the widget degrades to honest
empty states when the backend/repository is unavailable):
  - REMOTE mode: ``GET /api/v1/copilot/observability`` via the injected
    ``ApiClient`` (``client.get_copilot_observability()``).  On error the
    panel shows honest empty states instead of failing.
  - LOCAL mode: ``copilot_audit_log`` via ``CopilotAuditRepository._fetchall``
    (read-only aggregate queries — same pattern the router's undo endpoint
    uses), ``utils.observability.metrics`` for live confidence counters and
    per-phase timings recorded by ``PhaseTimer``
    (``copilot.phase.<PHASE>.count`` / ``.last_ms``), and
    ``backend.copilot.circuit_breaker`` in-memory per-company state.
  - ``backend.copilot.llm.registry.all_providers()`` for LLM provider health
    (health checks run on demand in a background thread — never on refresh).

Mount point: a ``QDockWidget`` in ``ui/main_window.py`` (already mounted;
toggle with Ctrl+Shift+O).  A standalone ``__main__`` smoke test is included:

    python -m ui.copilot.widgets.observability_panel
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from services.i18n import t

from ui.design_tokens import (
    COLOR_BG_CARD,
    COLOR_BG_ELEVATED,
    COLOR_BORDER_SUBTLE,
    COLOR_CHART_2,
    COLOR_CHART_3,
    COLOR_CHART_5,
    COLOR_ERROR_TEXT,
    COLOR_INFO_TEXT,
    COLOR_SUCCESS_TEXT,
    COLOR_TEXT_PRIMARY,
    COLOR_TEXT_SECONDARY,
    COLOR_TEXT_TERTIARY,
    COLOR_WARNING_TEXT,
    FONT_SIZE_BASE,
    FONT_SIZE_MD,
    FONT_SIZE_SM,
    FONT_SIZE_XL,
    FONT_SIZE_XS,
    FONT_WEIGHT_MEDIUM,
    FONT_WEIGHT_SEMIBOLD,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    SPACE_1,
    SPACE_2,
    SPACE_3,
)

logger = logging.getLogger(__name__)

# Confidence buckets — mirrors backend/copilot/confidence.py thresholds (§10).
HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.55

_MAX_BAR_WIDTH = 240  # px — longest confidence/rate bar

_CONFIDENCE_COLORS = {
    "high": COLOR_CHART_2,
    "medium": COLOR_CHART_3,
    "low": COLOR_CHART_5,
}


# ── Threaded LLM provider health check ─────────────────────────────────────


class _HealthCheckRunnable(QRunnable):
    """Runs ``provider.health_check()`` off the GUI thread.

    ``health_check`` is an async coroutine, so it is driven with ``asyncio.run``
    inside the worker thread; the result is delivered back to the panel via the
    ``provider_health_result`` signal (queued to the GUI thread).
    """

    def __init__(self, provider_id: str, provider: Any, emitter: QObject) -> None:
        super().__init__()
        self._provider_id = provider_id
        self._provider = provider
        self._emitter = emitter

    @Slot()
    def run(self) -> None:
        status = "down"
        try:
            import asyncio

            result = asyncio.run(self._provider.health_check())
            status = result or "down"
        except Exception as exc:  # network/provider SDK errors → down
            logger.debug("Provider health check failed for %s: %s", self._provider_id, exc)
            status = "down"
        self._emitter.provider_health_result.emit(self._provider_id, status)


# ── Small building blocks ──────────────────────────────────────────────────


def _make_label(
    text: str,
    color: str = COLOR_TEXT_PRIMARY,
    size: int = FONT_SIZE_BASE,
    weight: int = FONT_WEIGHT_MEDIUM,
    parent: Optional[QWidget] = None,
) -> QLabel:
    label = QLabel(text, parent)
    label.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: {weight}; background: transparent;"
    )
    return label


class _MetricCard(QFrame):
    """Small KPI card — value on top, label underneath."""

    def __init__(self, parent: Optional[QWidget], title: str) -> None:
        super().__init__(parent)
        self.setObjectName("obs-metric-card")
        self.setStyleSheet(
            f"#obs-metric-card {{ background-color: {COLOR_BG_CARD}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: {RADIUS_MD}px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_2)
        layout.setSpacing(SPACE_1)

        self._value_lbl = _make_label("—", COLOR_TEXT_PRIMARY, FONT_SIZE_XL, FONT_WEIGHT_SEMIBOLD, self)
        self._value_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._value_lbl)

        self._title_lbl = _make_label(title, COLOR_TEXT_TERTIARY, FONT_SIZE_XS, FONT_WEIGHT_MEDIUM, self)
        self._title_lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._title_lbl)

    def set_value(self, value: str, color: str = COLOR_TEXT_PRIMARY) -> None:
        self._value_lbl.setText(value)
        self._value_lbl.setStyleSheet(
            f"color: {color}; font-size: {FONT_SIZE_XL}px; "
            f"font-weight: {FONT_WEIGHT_SEMIBOLD}; background: transparent;"
        )


class _Section(QFrame):
    """Outlined section card with a title header."""

    def __init__(self, parent: Optional[QWidget], title: str) -> None:
        super().__init__(parent)
        self.setObjectName("obs-section")
        self.setStyleSheet(
            f"#obs-section {{ background-color: {COLOR_BG_ELEVATED}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: {RADIUS_LG}px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE_3, SPACE_2, SPACE_3, SPACE_3)
        layout.setSpacing(SPACE_2)

        header = _make_label(title, COLOR_TEXT_PRIMARY, FONT_SIZE_MD, FONT_WEIGHT_SEMIBOLD, self)
        layout.addWidget(header)
        self._body = layout

    def body(self) -> QVBoxLayout:
        return self._body

    def set_empty(self, message: str) -> None:
        """Replace the body with a single honest empty-state hint."""
        self._clear_body()
        hint = _make_label(message, COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self)
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        self._body.addWidget(hint)

    def _clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


def _format_rate(fraction: Optional[float]) -> str:
    if fraction is None:
        return "—"
    return f"{fraction * 100:.1f}%"


# ── Observability panel ────────────────────────────────────────────────────


class ObservabilityPanel(QFrame):
    """Dev-toolkit Co-Pilot observability panel (§23.6).

    Constructor accepts injected dependencies (``db``/``audit_repo``,
    ``metrics``, ``circuit_breaker``, ``providers``, ``api_client``) so it is
    unit-testable; when omitted, real backend singletons are resolved lazily
    and guarded.

    When ``api_client`` is provided the panel fetches
    ``GET /api/v1/copilot/observability`` (REMOTE mode) and falls back to
    honest empty states on error; without it the panel reads the local DB and
    in-memory singletons exactly as before (LOCAL mode).
    """

    provider_health_result = Signal(str, str)  # provider_id, status

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        db: Any = None,
        audit_repo: Any = None,
        company_id: int = 0,
        metrics: Any = None,
        circuit_breaker: Any = None,
        providers: Optional[Dict[str, Any]] = None,
        api_client: Any = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("observability-panel")
        self.setStyleSheet(
            f"#observability-panel {{ background-color: {COLOR_BG_ELEVATED}; "
            f"border: 1px solid {COLOR_BORDER_SUBTLE}; border-radius: {RADIUS_LG}px; }}"
        )

        self._db = db
        self._audit_repo = audit_repo
        self._company_id = company_id
        self._metrics = metrics
        self._circuit_breaker = circuit_breaker
        self._providers = providers
        self._api_client = api_client
        self._health_state: Dict[str, str] = {}
        self._provider_rows: Dict[str, QLabel] = {}
        self._thread_pool = QThreadPool.globalInstance()

        self.provider_health_result.connect(self._on_provider_health_result)

        self._build_ui()
        self.refresh()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(SPACE_3, SPACE_3, SPACE_3, SPACE_3)
        root_layout.setSpacing(SPACE_3)

        # Header row
        header = QWidget(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACE_2)

        title_col = QWidget(header)
        title_layout = QVBoxLayout(title_col)
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(0)
        title_layout.addWidget(
            _make_label("Co-Pilot Observability", COLOR_TEXT_PRIMARY, FONT_SIZE_MD, FONT_WEIGHT_SEMIBOLD, title_col)
        )
        self._subtitle_lbl = _make_label(
            "Dev-toolkit · live signals from the Co-Pilot runtime",
            COLOR_TEXT_TERTIARY,
            FONT_SIZE_XS,
            FONT_WEIGHT_MEDIUM,
            title_col,
        )
        title_layout.addWidget(self._subtitle_lbl)
        header_layout.addWidget(title_col, 1)

        self._last_updated_lbl = _make_label("", COLOR_TEXT_TERTIARY, FONT_SIZE_XS, FONT_WEIGHT_MEDIUM, header)
        header_layout.addWidget(self._last_updated_lbl)

        refresh_btn = QPushButton(t("copilot.observability.refresh", default="Refresh"), header)
        refresh_btn.setProperty("variant", "primary")
        refresh_btn.setFixedHeight(28)
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        root_layout.addWidget(header)

        # Scrollable content
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")
        content = QWidget(scroll)
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(SPACE_3)
        self._content_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(content)
        root_layout.addWidget(scroll, 1)

        # ── KPI row ─────────────────────────────────────────────────────
        kpi_row = QWidget(content)
        kpi_layout = QHBoxLayout(kpi_row)
        kpi_layout.setContentsMargins(0, 0, 0, 0)
        kpi_layout.setSpacing(SPACE_2)
        self._kpi_failure = _MetricCard(kpi_row, "Tool failure rate")
        self._kpi_abandonment = _MetricCard(kpi_row, "Abandonment rate")
        self._kpi_trips = _MetricCard(kpi_row, "Circuit-breaker trips")
        self._kpi_phases = _MetricCard(kpi_row, "Phase samples")
        for card in (self._kpi_failure, self._kpi_abandonment, self._kpi_trips, self._kpi_phases):
            card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            kpi_layout.addWidget(card, 1)
        self._content_layout.addWidget(kpi_row)

        # ── Confidence distribution ─────────────────────────────────────
        self._confidence_section = _Section(content, "Confidence distribution")
        self._confidence_body = QVBoxLayout()
        self._confidence_section.body().addLayout(self._confidence_body)
        self._content_layout.addWidget(self._confidence_section)

        # ── Phase timings ───────────────────────────────────────────────
        self._phase_section = _Section(content, "Phase timings (last_ms)")
        self._phase_body = QVBoxLayout()
        self._phase_section.body().addLayout(self._phase_body)
        self._content_layout.addWidget(self._phase_section)

        # ── Circuit breaker ─────────────────────────────────────────────
        self._cb_section = _Section(content, "Circuit breaker (in-memory)")
        self._cb_body = QVBoxLayout()
        self._cb_section.body().addLayout(self._cb_body)
        self._content_layout.addWidget(self._cb_section)

        # ── LLM providers ───────────────────────────────────────────────
        self._provider_section = _Section(content, "LLM provider health")
        self._provider_body = QVBoxLayout()
        self._provider_section.body().addLayout(self._provider_body)
        self._content_layout.addWidget(self._provider_section)

        # ── Audit log note ──────────────────────────────────────────────
        self._audit_note = _make_label(
            "Rates are sampled from the copilot_audit_log table.",
            COLOR_TEXT_TERTIARY,
            FONT_SIZE_XS,
            FONT_WEIGHT_MEDIUM,
            content,
        )
        self._content_layout.addWidget(self._audit_note)

    # ── Data-source resolution (guarded) ────────────────────────────────

    def _get_metrics(self) -> Any:
        if self._metrics is not None:
            return self._metrics
        try:
            from utils.observability import metrics
            return metrics
        except Exception:
            return None

    def _get_circuit_breaker(self) -> Any:
        if self._circuit_breaker is not None:
            return self._circuit_breaker
        try:
            from backend.copilot.circuit_breaker import get_circuit_breaker
            return get_circuit_breaker()
        except Exception:
            return None

    def _get_audit_repo(self) -> Any:
        if self._audit_repo is not None:
            return self._audit_repo
        try:
            from repositories.copilot_repository import CopilotAuditRepository
            if self._db is not None:
                return CopilotAuditRepository(self._db)
            from backend.config import BackendSettings
            from database.db_manager import DatabaseManager

            config = BackendSettings()
            return CopilotAuditRepository(DatabaseManager(config.db_path))
        except Exception:
            return None

    def _get_providers(self) -> Dict[str, Any]:
        if self._providers is not None:
            return self._providers
        try:
            from backend.copilot.llm.registry import all_providers
            return all_providers()
        except Exception:
            return {}

    def _get_api_client(self) -> Any:
        """Return the injected ApiClient (``None`` → LOCAL mode)."""
        return self._api_client

    # ── Public API ──────────────────────────────────────────────────────

    def refresh(self) -> None:
        """Re-read every data source and rebuild the section contents.

        REMOTE mode (an ``api_client`` was injected) fetches the backend
        observability endpoint; LOCAL mode reads the local DB and in-memory
        singletons.  Provider health is local in both modes.
        """
        if self._get_api_client() is not None:
            self._refresh_remote_section()
        else:
            self._refresh_metrics_section()
            self._refresh_audit_section()
            self._refresh_circuit_breaker_section()
        self._refresh_providers_section()
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        self._last_updated_lbl.setText(f"updated {now} UTC")

    def run_provider_health_checks(self) -> None:
        """Kick off LLM provider health checks in a background thread."""
        providers = self._get_providers()
        if not providers:
            return
        for provider_id, provider in providers.items():
            self._health_state[provider_id] = "checking…"
            label = self._provider_rows.get(provider_id)
            if label is not None:
                label.setText(self._status_text("checking…"))
            runnable = _HealthCheckRunnable(provider_id, provider, self)
            self._thread_pool.start(runnable)

    # ── Section refreshers ──────────────────────────────────────────────

    def _refresh_metrics_section(self) -> None:
        metrics = self._get_metrics()
        phase_rows = []
        if metrics is not None:
            try:
                snapshot = metrics.snapshot()
            except Exception:
                snapshot = {}
            counters = snapshot.get("counters", {}) or {}
            gauges = snapshot.get("gauges", {}) or {}
            for key, count in counters.items():
                if key.startswith("copilot.phase.") and key.endswith(".count"):
                    phase_name = key[len("copilot.phase."):-len(".count")]
                    last_ms = gauges.get(f"copilot.phase.{phase_name}.last_ms")
                    phase_rows.append((phase_name, int(count), last_ms))
        phase_rows.sort(key=lambda r: r[2] if r[2] is not None else -1, reverse=True)

        total_samples = sum(row[1] for row in phase_rows)
        self._kpi_phases.set_value(str(total_samples))

        self._clear_layout(self._phase_body)
        if not phase_rows:
            hint = _make_label(
                "No phase timings recorded yet — PhaseTimer is not wrapping the "
                "pipeline in production (planner/executor/router are owned by "
                "other lanes).",
                COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._phase_section,
            )
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            self._phase_body.addWidget(hint)
            return

        for phase_name, count, last_ms in phase_rows:
            self._render_phase_row(phase_name, count, last_ms)

    def _refresh_audit_section(self) -> None:
        repo = self._get_audit_repo()
        if repo is None:
            self._kpi_failure.set_value("—")
            self._kpi_abandonment.set_value("—")
            self._audit_note.setText(t(
                "copilot.observability.audit_log_unavailable",
                default="copilot_audit_log unavailable — rates show as em dash.",
            ))
            self._set_confidence_empty(
                "No audit log available — confidence distribution unavailable."
            )
            return

        company_filter = " AND company_id = ?" if self._company_id else ""
        params: tuple = (self._company_id,) if self._company_id else ()

        stats = {"confidence": None, "tool_failures": None, "abandonment": None}
        schema_note = ""
        try:
            # Confidence distribution from stored confidence_score (§10 buckets).
            # The column exists in both the SQLite (schema.py) and the Alembic
            # table definitions.
            rows = repo._fetchall(
                "SELECT "
                " COALESCE(SUM(CASE WHEN confidence_score >= ? THEN 1 ELSE 0 END),0) AS high, "
                " COALESCE(SUM(CASE WHEN confidence_score >= ? AND confidence_score < ? THEN 1 ELSE 0 END),0) AS medium, "
                " COALESCE(SUM(CASE WHEN confidence_score < ? THEN 1 ELSE 0 END),0) AS low "
                " FROM copilot_audit_log WHERE confidence_score IS NOT NULL" + company_filter,
                (HIGH_CONFIDENCE_THRESHOLD, MEDIUM_CONFIDENCE_THRESHOLD,
                 HIGH_CONFIDENCE_THRESHOLD, MEDIUM_CONFIDENCE_THRESHOLD, *params),
            ) or [{}]
            stats["confidence"] = rows[0]

            # Tool failure / abandonment — the SQLite schema writes an
            # ``action`` column (tool_execution_*); the Alembic migration
            # schema instead carries ``status``.  Try ``action`` first, fall
            # back to ``status``.
            stats, schema_note = self._query_audit_rates(repo, company_filter, params, stats)

            total_rows = repo._fetchone(
                "SELECT COUNT(*) AS total FROM copilot_audit_log" + company_filter,
                params,
            )
            row_count = (total_rows or {}).get("total", 0)
            note = f"Sampled from {row_count} copilot_audit_log row(s)"
            if schema_note:
                note += f" · schema: {schema_note}"
            self._audit_note.setText(note + ".")
        except Exception as exc:
            logger.warning("ObservabilityPanel: audit query failed: %s", exc)
            stats = {"confidence": None, "tool_failures": None, "abandonment": None}
            self._audit_note.setText(t(
                "copilot.observability.audit_query_failed",
                default="Audit query failed — see backend logs.",
            ))

        # ── KPI values ─────────────────────────────────────────────────
        tool = stats["tool_failures"]
        if tool and tool.get("total"):
            failure_rate = tool["failures"] / tool["total"]
            self._kpi_failure.set_value(_format_rate(failure_rate), COLOR_ERROR_TEXT)
        else:
            self._kpi_failure.set_value("—")

        abandon = stats["abandonment"]
        if abandon and abandon.get("started"):
            abandoned = max(0, abandon["started"] - abandon["finished"])
            self._kpi_abandonment.set_value(_format_rate(abandoned / abandon["started"]), COLOR_WARNING_TEXT)
        else:
            self._kpi_abandonment.set_value("—")

        # ── Confidence distribution (§23.6) ────────────────────────────
        # Live metrics counters first (the planner increments these per plan),
        # then fall back to the stored confidence_score derivation.
        live = self._live_confidence_counters()
        if live is not None:
            self._render_confidence(high=live[0], medium=live[1], low=live[2])
            return
        conf = stats["confidence"]
        if conf and (conf.get("high") or conf.get("medium") or conf.get("low")):
            self._render_confidence(high=conf.get("high", 0), medium=conf.get("medium", 0), low=conf.get("low", 0))
        else:
            self._set_confidence_empty(
                "No confidence scores stored yet — the audit log does not record "
                "confidence_score for current tool writes."
            )

    def _query_audit_rates(
        self,
        repo: Any,
        company_filter: str,
        params: tuple,
        stats: Dict[str, Any],
    ) -> tuple:
        """Query tool failure + abandonment rates, tolerating either schema.

        Returns ``(stats, schema_note)``.  ``action``-based queries target the
        SQLite schema (``tool_execution_*`` actions written by audit.py);
        ``status``-based queries target the Alembic migration schema.
        """
        try:
            rows = repo._fetchall(
                "SELECT COUNT(*) AS total, "
                " COALESCE(SUM(CASE WHEN action = 'tool_execution_failed' THEN 1 ELSE 0 END),0) AS failures, "
                " COALESCE(SUM(CASE WHEN action = 'tool_execution_succeeded' THEN 1 ELSE 0 END),0) AS successes "
                " FROM copilot_audit_log "
                " WHERE action IN ('tool_execution_start','tool_execution_succeeded','tool_execution_failed')"
                + company_filter,
                params,
            ) or [{}]
            stats["tool_failures"] = rows[0]

            rows = repo._fetchall(
                "SELECT COUNT(DISTINCT conversation_id) AS conversations, "
                " COUNT(DISTINCT CASE WHEN action = 'tool_execution_start' THEN conversation_id END) AS started, "
                " COUNT(DISTINCT CASE WHEN action IN ('tool_execution_succeeded','tool_execution_failed') "
                "   THEN conversation_id END) AS finished "
                " FROM copilot_audit_log "
                " WHERE conversation_id IS NOT NULL AND conversation_id != ''" + company_filter,
                params,
            ) or [{}]
            stats["abandonment"] = rows[0]
            return stats, "action column"
        except Exception:
            logger.debug("ObservabilityPanel: action-column queries unavailable, trying status column")

        try:
            rows = repo._fetchall(
                "SELECT COUNT(*) AS total, "
                " COALESCE(SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END),0) AS failures, "
                " COALESCE(SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END),0) AS successes "
                " FROM copilot_audit_log "
                " WHERE status IN ('succeeded','failed')" + company_filter,
                params,
            ) or [{}]
            stats["tool_failures"] = rows[0]

            rows = repo._fetchall(
                "SELECT COUNT(DISTINCT conversation_id) AS started, "
                " COUNT(DISTINCT CASE WHEN status = 'succeeded' THEN conversation_id END) AS finished "
                " FROM copilot_audit_log "
                " WHERE status IS NOT NULL AND status != ''" + company_filter,
                params,
            ) or [{}]
            stats["abandonment"] = rows[0]
            return stats, "status column"
        except Exception as exc:
            logger.debug("ObservabilityPanel: status-column queries also unavailable: %s", exc)
            stats["tool_failures"] = None
            stats["abandonment"] = None
            return stats, "unavailable"

    def _refresh_circuit_breaker_section(self) -> None:
        cb = self._get_circuit_breaker()
        self._clear_layout(self._cb_body)
        if cb is None:
            self._kpi_trips.set_value("—")
            hint = _make_label(
                "Circuit breaker module unavailable.",
                COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._cb_section,
            )
            hint.setAlignment(Qt.AlignCenter)
            self._cb_body.addWidget(hint)
            return

        try:
            states = getattr(cb, "_states", {}) or {}
        except Exception:
            states = {}
        tripped = [s for s in states.values() if getattr(s, "tripped", False)]
        self._kpi_trips.set_value(str(len(tripped)), COLOR_ERROR_TEXT if tripped else COLOR_TEXT_PRIMARY)

        if not states:
            hint = _make_label(
                "No autonomous-action activity tracked yet — the breaker only "
                "records companies that actually executed a tool.",
                COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._cb_section,
            )
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            self._cb_body.addWidget(hint)
            return

        summary = _make_label(
            f"{len(states)} company breaker(s) tracked · {len(tripped)} tripped",
            COLOR_TEXT_SECONDARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._cb_section,
        )
        self._cb_body.addWidget(summary)

        for state in sorted(states.values(), key=lambda s: getattr(s, "company_id", 0)):
            self._render_circuit_breaker_row(
                getattr(state, "company_id", 0),
                bool(getattr(state, "tripped", False)),
                getattr(state, "tripped_reason", None) or "",
            )

    def _refresh_providers_section(self) -> None:
        providers = self._get_providers()
        self._clear_layout(self._provider_body)
        self._provider_rows.clear()

        if not providers:
            hint = _make_label(
                "No LLM providers registered — provider modules are imported on "
                "demand and are not loaded in the dev-toolkit yet.",
                COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._provider_section,
            )
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignCenter)
            self._provider_body.addWidget(hint)
            return

        check_btn = QPushButton(t("copilot.observability.check_all_providers", default="Check all providers"), self._provider_section)
        check_btn.setProperty("variant", "ghost")
        check_btn.setFixedHeight(26)
        check_btn.clicked.connect(self.run_provider_health_checks)
        self._provider_body.addWidget(check_btn)

        for provider_id, provider in providers.items():
            row = QWidget(self._provider_section)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SPACE_2)
            model_id = getattr(provider, "model_id", "?")
            row_layout.addWidget(_make_label(
                f"{provider_id} · {model_id}", COLOR_TEXT_PRIMARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row,
            ))
            row_layout.addStretch(1)
            status = self._health_state.get(provider_id, "not checked")
            status_lbl = _make_label(self._status_text(status), COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row)
            self._provider_rows[provider_id] = status_lbl
            row_layout.addWidget(status_lbl)
            self._provider_body.addWidget(row)

    # ── Rendering helpers ───────────────────────────────────────────────

    def _refresh_remote_section(self) -> None:
        """Fetch backend observability aggregates via the injected ApiClient.

        On success renders KPIs, confidence distribution, phase timings and
        circuit-breaker state from the endpoint payload.  On any error the
        panel shows honest empty states (no silent local fallback).
        """
        client = self._get_api_client()
        data = None
        try:
            get_method = getattr(client, "get_copilot_observability", None)
            if get_method is None:
                generic_get = getattr(client, "_get", None) or getattr(client, "get", None)
                data = generic_get("/api/v1/copilot/observability") if generic_get else None
            else:
                data = get_method()
        except Exception as exc:
            logger.warning("ObservabilityPanel: remote observability fetch failed: %s", exc)
            data = None

        if not isinstance(data, dict):
            self._kpi_failure.set_value("—")
            self._kpi_abandonment.set_value("—")
            self._kpi_trips.set_value("—")
            self._kpi_phases.set_value("—")
            self._audit_note.setText(t(
                "copilot.observability.remote_unavailable",
                default="Remote observability endpoint unavailable — showing empty state.",
            ))
            self._set_confidence_empty("Remote observability endpoint unavailable.")
            self._set_phase_empty("No phase timings received from the server.")
            self._set_circuit_breaker_empty("No circuit-breaker state received from the server.")
            return

        # ── KPIs ──────────────────────────────────────────────────────
        tool = data.get("tool_failures") or {}
        if tool.get("total"):
            failure_rate = tool.get("failures", 0) / tool["total"]
            self._kpi_failure.set_value(_format_rate(failure_rate), COLOR_ERROR_TEXT)
        else:
            self._kpi_failure.set_value("—")

        abandon = data.get("abandonment") or {}
        started = abandon.get("started", 0)
        if started:
            abandoned = max(0, started - abandon.get("finished", 0))
            self._kpi_abandonment.set_value(_format_rate(abandoned / started), COLOR_WARNING_TEXT)
        else:
            self._kpi_abandonment.set_value("—")

        cb = data.get("circuit_breaker") or {}
        tripped_count = int(cb.get("tripped", 0) or 0)
        self._kpi_trips.set_value(
            str(tripped_count), COLOR_ERROR_TEXT if tripped_count else COLOR_TEXT_PRIMARY
        )

        phases = data.get("phase_timings") or []
        self._kpi_phases.set_value(str(sum(int(p.get("count", 0) or 0) for p in phases)))

        # ── Phase timings ─────────────────────────────────────────────
        self._clear_layout(self._phase_body)
        if phases:
            for p in phases:
                self._render_phase_row(p.get("phase", "?"), int(p.get("count", 0) or 0), p.get("last_ms"))
        else:
            self._set_phase_empty("No phase timings recorded on the server yet.")

        # ── Circuit breaker ───────────────────────────────────────────
        self._clear_layout(self._cb_body)
        companies = cb.get("companies") or []
        if companies:
            summary = _make_label(
                f"{cb.get('tracked', len(companies))} company breaker(s) tracked · "
                f"{tripped_count} tripped",
                COLOR_TEXT_SECONDARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._cb_section,
            )
            self._cb_body.addWidget(summary)
            for c in companies:
                self._render_circuit_breaker_row(
                    c.get("company_id", 0),
                    bool(c.get("tripped", False)),
                    c.get("tripped_reason", "") or "",
                )
        else:
            self._set_circuit_breaker_empty(
                "No autonomous-action activity tracked yet — the breaker only "
                "records companies that actually executed a tool."
            )

        # ── Confidence distribution ───────────────────────────────────
        conf = data.get("confidence") or {}
        if conf and (conf.get("high") or conf.get("medium") or conf.get("low")):
            self._render_confidence(
                high=conf.get("high", 0), medium=conf.get("medium", 0), low=conf.get("low", 0)
            )
        else:
            self._set_confidence_empty("No confidence scores recorded on the server yet.")

        self._audit_note.setText(
            f"Remote server · {data.get('audit_rows', 0)} copilot_audit_log row(s) sampled."
        )

    def _live_confidence_counters(self) -> Optional[Tuple[int, int, int]]:
        """Return ``(high, medium, low)`` from live metrics counters when present.

        The planner increments ``copilot.confidence.high/medium/low`` in
        ``utils.observability.metrics`` per plan.  Returns ``None`` when no
        counter has been incremented yet (caller falls back to audit-log
        derivation).
        """
        metrics = self._get_metrics()
        if metrics is None:
            return None
        try:
            counters = metrics.snapshot().get("counters", {}) or {}
        except Exception:
            return None
        high = int(counters.get("copilot.confidence.high", 0))
        medium = int(counters.get("copilot.confidence.medium", 0))
        low = int(counters.get("copilot.confidence.low", 0))
        if high or medium or low:
            return (high, medium, low)
        return None

    def _render_phase_row(self, phase_name: str, count: int, last_ms: Any) -> None:
        """Append one phase-timing row to ``self._phase_body``."""
        row = QWidget(self._phase_section)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SPACE_2)
        row_layout.addWidget(_make_label(phase_name, COLOR_TEXT_PRIMARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row))
        row_layout.addStretch(1)
        ms_text = f"{last_ms:.1f} ms" if isinstance(last_ms, (int, float)) else "—"
        row_layout.addWidget(
            _make_label(f"{count}x · {ms_text}", COLOR_TEXT_SECONDARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row)
        )
        self._phase_body.addWidget(row)

    def _render_circuit_breaker_row(self, company_id: Any, tripped: bool, reason: str) -> None:
        """Append one circuit-breaker row to ``self._cb_body``."""
        row = QWidget(self._cb_section)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(SPACE_2)
        status = "TRIPPED" if tripped else "closed"
        color = COLOR_ERROR_TEXT if tripped else COLOR_SUCCESS_TEXT
        row_layout.addWidget(_make_label(
            f"company #{company_id}", COLOR_TEXT_PRIMARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row,
        ))
        row_layout.addStretch(1)
        suffix = f" — {reason}" if reason else ""
        row_layout.addWidget(_make_label(
            f"{status}{suffix}", color, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row,
        ))
        self._cb_body.addWidget(row)

    def _render_confidence(self, high: int, medium: int, low: int) -> None:
        self._clear_layout(self._confidence_body)
        total = high + medium + low
        if total <= 0:
            return
        buckets = [("high", high), ("medium", medium), ("low", low)]
        max_count = max(count for _, count in buckets) or 1
        title = _make_label(
            f"{total} scored plan(s)", COLOR_TEXT_SECONDARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._confidence_section,
        )
        self._confidence_body.addWidget(title)
        for name, count in buckets:
            row = QWidget(self._confidence_section)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(SPACE_2)
            row_layout.addWidget(_make_label(name, COLOR_TEXT_SECONDARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row))
            bar_width = max(int(_MAX_BAR_WIDTH * count / max_count), 4) if count else 4
            bar = QFrame(row)
            bar.setFixedHeight(10)
            bar.setFixedWidth(bar_width)
            bar.setStyleSheet(
                f"background-color: {_CONFIDENCE_COLORS[name]}; border-radius: {RADIUS_SM}px; border: none;"
            )
            row_layout.addWidget(bar)
            row_layout.addSpacing(SPACE_2)
            row_layout.addWidget(_make_label(str(count), COLOR_TEXT_PRIMARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, row))
            row_layout.addStretch(1)
            self._confidence_body.addWidget(row)

    def _set_confidence_empty(self, message: str) -> None:
        self._clear_layout(self._confidence_body)
        hint = _make_label(message, COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._confidence_section)
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        self._confidence_body.addWidget(hint)

    def _set_phase_empty(self, message: str) -> None:
        self._clear_layout(self._phase_body)
        hint = _make_label(message, COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._phase_section)
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        self._phase_body.addWidget(hint)

    def _set_circuit_breaker_empty(self, message: str) -> None:
        self._clear_layout(self._cb_body)
        hint = _make_label(message, COLOR_TEXT_TERTIARY, FONT_SIZE_SM, FONT_WEIGHT_MEDIUM, self._cb_section)
        hint.setWordWrap(True)
        hint.setAlignment(Qt.AlignCenter)
        self._cb_body.addWidget(hint)

    def _status_text(self, status: str) -> str:
        color = {
            "healthy": COLOR_SUCCESS_TEXT,
            "degraded": COLOR_WARNING_TEXT,
            "down": COLOR_ERROR_TEXT,
            "checking…": COLOR_INFO_TEXT,
        }.get(status, COLOR_TEXT_TERTIARY)
        return f"<span style='color:{color};'>{status}</span>"

    def _on_provider_health_result(self, provider_id: str, status: str) -> None:
        self._health_state[provider_id] = status
        label = self._provider_rows.get(provider_id)
        if label is not None:
            label.setText(self._status_text(status))

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()


if __name__ == "__main__":  # pragma: no cover — standalone smoke test
    import os
    import sys

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    class _FakeRemoteClient:
        """Minimal ApiClient stand-in that returns a canned endpoint payload."""

        def get_copilot_observability(self):
            return {
                "tool_failures": {"total": 10, "failures": 2, "successes": 8},
                "abandonment": {"started": 4, "finished": 3},
                "confidence": {"high": 5, "medium": 3, "low": 2},
                "circuit_breaker": {
                    "tracked": 2, "tripped": 1,
                    "companies": [
                        {"company_id": 1, "tripped": True, "tripped_reason": "Max consecutive failures"},
                        {"company_id": 2, "tripped": False, "tripped_reason": ""},
                    ],
                },
                "phase_timings": [
                    {"phase": "PIPELINE", "count": 12, "last_ms": 123.4},
                    {"phase": "UNDERSTAND", "count": 5, "last_ms": 42.0},
                ],
                "audit_rows": 10,
            }

    class _FailingRemoteClient:
        def get_copilot_observability(self):
            raise RuntimeError("endpoint unreachable")

    app = QApplication.instance() or QApplication(sys.argv)

    # LOCAL mode (no api_client) — sections constructed and refreshed.
    panel = ObservabilityPanel()
    panel.resize(560, 640)
    panel.refresh()
    panel.show()
    app.processEvents()
    print("ObservabilityPanel smoke test (LOCAL) passed — sections constructed and refreshed.")

    # REMOTE mode with a fake client — endpoint payload rendered.
    remote_panel = ObservabilityPanel(api_client=_FakeRemoteClient())
    remote_panel.refresh()
    assert remote_panel._kpi_failure._value_lbl.text() == "20.0%", (
        remote_panel._kpi_failure._value_lbl.text()
    )
    assert remote_panel._kpi_trips._value_lbl.text() == "1"
    assert remote_panel._kpi_phases._value_lbl.text() == "17"
    print("ObservabilityPanel smoke test (REMOTE) passed — endpoint payload rendered.")

    # REMOTE mode with a failing client — honest empty states.
    failing_panel = ObservabilityPanel(api_client=_FailingRemoteClient())
    failing_panel.refresh()
    assert failing_panel._kpi_failure._value_lbl.text() == "—"
    print("ObservabilityPanel smoke test (REMOTE error) passed — empty state on failure.")

    panel.close()
    remote_panel.close()
    failing_panel.close()
    sys.exit(0)

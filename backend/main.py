from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

# Load .env before any config is read
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path)
except Exception:
    pass

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.v1.router import api_v1_router
from backend.config import BackendSettings
from backend.logging_config import configure_backend_logging
from backend.metrics import PrometheusMiddleware
from backend.middleware.auth_middleware import AuthMiddleware
from backend.middleware.correlation_middleware import CorrelationMiddleware
from backend.middleware.idempotency_middleware import IdempotencyMiddleware
from backend.middleware.logging_middleware import LoggingMiddleware
from backend.middleware.rate_limit_middleware import RateLimitMiddleware
from backend.middleware.input_sanitization_middleware import InputSanitizationMiddleware
from backend.middleware.security_headers_middleware import SecurityHeadersMiddleware
from backend.middleware.webhook_middleware import WebhookBodyMiddleware

logger = logging.getLogger(__name__)


def _init_sentry() -> None:
    """Initialise the Sentry SDK from ``OPERION_SENTRY_DSN`` (no-op when unset).

    Mirrors the mobile guard: no DSN → nothing is initialised and every
    ``capture_exception`` stays a no-op.  Failures to initialise are logged
    but never block startup.
    """
    dsn = os.environ.get("OPERION_SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=0.1,
            environment=os.environ.get("OPERION_ENV", "development"),
        )
        logger.info("Sentry initialised (environment=%s)", os.environ.get("OPERION_ENV", "development"))
    except Exception as exc:
        logger.warning("Sentry initialisation failed: %s", exc)


def _capture_exception(exc: BaseException) -> None:
    """Forward *exc* to Sentry when the SDK is enabled; never raises.

    ``sentry_sdk.get_client()`` only exists on sentry-sdk >= 2.0.  Gated so a
    missing/uninitialised SDK is a strict no-op in any environment.
    """
    try:
        import sentry_sdk
        if sentry_sdk.get_client().is_enabled():
            sentry_sdk.capture_exception(exc)
    except Exception:
        pass  # Sentry absent or not initialised — never break request handling.


def create_app(settings: Optional[BackendSettings] = None) -> FastAPI:
    if settings is None:
        settings = BackendSettings()

    # JSON logging (F5 observability): one JSON object per log line, with
    # request_id when present on the record.  Idempotent — preserves any
    # logging already configured by gunicorn (only swaps formatters).
    configure_backend_logging()

    # Sentry error tracking — no-op when OPERION_SENTRY_DSN is absent.
    _init_sentry()

    env_mode = os.environ.get("OPERION_ENV", "development")
    is_production = env_mode == "production"

    app = FastAPI(
        title="Operion ERP API",
        version="1.0.0",
        docs_url="/docs" if not is_production else None,
        redoc_url="/redoc" if not is_production else None,
        openapi_url="/openapi.json" if not is_production else None,
    )

    allowed_origins = os.environ.get(
        "OPERION_CORS_ORIGINS",
        "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
        if not is_production
        else "https://operionerp.xyz,https://app.operionerp.xyz,https://api.operionerp.xyz",
    ).split(",")

    # In development, allow any localhost origin (Flutter web uses random ports).
    cors_kwargs = dict(
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-API-Key"],
    )
    if not is_production:
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1|operionerp\.xyz|.*\.operionerp\.xyz)(:\d+)?"
        cors_kwargs["allow_origins"] = []
    else:
        cors_kwargs["allow_origins"] = allowed_origins

    app.add_middleware(CORSMiddleware, **cors_kwargs)

    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(AuthMiddleware)
    # Security headers on ALL responses (after auth, before business logic)
    app.add_middleware(
        SecurityHeadersMiddleware,
        is_production=is_production,
        cors_origins=allowed_origins,
    )
    # Idempotency middleware before rate limiter so replayed keys aren't counted
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(WebhookBodyMiddleware)
    app.add_middleware(PrometheusMiddleware)
    # Input sanitization — strips dangerous characters and neutralises
    # injection patterns from all JSON request bodies (defence-in-depth).
    app.add_middleware(InputSanitizationMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        from backend.middleware.correlation_middleware import get_correlation_id
        from backend.errors import ProblemDetail, get_error_code_for_exception

        error_code, status = get_error_code_for_exception(exc)

        # Extract detail, handling HTTPException's dict-formatted detail
        detail = str(exc)
        error_code_value = error_code.value
        if hasattr(exc, "detail"):
            if isinstance(exc.detail, dict):
                detail = exc.detail.get("detail", detail)
                if "error_code" in exc.detail:
                    error_code_value = exc.detail["error_code"]
            elif isinstance(exc.detail, str):
                detail = exc.detail

        problem = ProblemDetail(
            type=f"https://api.operionerp.xyz/errors/{error_code_value}",
            title="An error occurred",
            status=status,
            detail=detail,
            instance=str(request.url),
            error_code=error_code_value,
        )

        logger.error("Unhandled error [%s]: %s %s — %s",
                     get_correlation_id(), request.method, request.url.path, exc,
                     exc_info=True, extra={"request_id": get_correlation_id()})

        _capture_exception(exc)

        return JSONResponse(status_code=status, content=problem.to_dict())

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        from backend.errors import ProblemDetail, get_error_code_for_exception
        from backend.middleware.correlation_middleware import get_correlation_id

        error_code, status = get_error_code_for_exception(exc)
        problem = ProblemDetail(
            type=f"https://api.operionerp.xyz/errors/{error_code}",
            title="Internal server error",
            status=status,
            detail="An unexpected error occurred. Please try again later.",
            instance=str(request.url),
            error_code=error_code.value,
        )
        logger.error("500 error on %s %s: %s", request.method, request.url.path, exc,
                     exc_info=True, extra={"request_id": get_correlation_id()})

        _capture_exception(exc)

        return JSONResponse(status_code=status, content=problem.to_dict())

    app.include_router(api_v1_router)

    # ── Warm the router match caches (F5, spurious-404 fix) ───────────────
    # FastAPI >= 0.139 defers route flattening: ``include_router`` stores an
    # ``_IncludedRouter`` per sub-router and lazily builds the effective
    # candidate list on the first request.  That lazy rebuild is not
    # thread-safe — a burst of concurrent requests against a fresh app can
    # observe an empty/partial candidate list and return spurious 404
    # "Not Found" for valid routes.  Walking the router tree once here
    # populates every cache before any request can race on them.
    try:
        for _route in app.router.routes:
            _route.matches({
                "type": "http",
                "method": "GET",
                "path": "/__operion_route_warmup__",
                "headers": [],
                "query_string": b"",
                "scheme": "http",
                "root_path": "",
                "server": ("127.0.0.1", 80),
                "client": ("127.0.0.1", 12345),
                "app": app,
            })
    except Exception:
        # Warm-up is purely defensive — a failure here must never block startup.
        logger.debug("Router cache warm-up skipped: %s", exc_info=True)

    # ── Hourly idempotency-store cleanup (F5) ─────────────────────────────
    # ``cleanup_expired_entries()`` prunes expired in-memory idempotency
    # entries + their per-key locks.  Redis entries expire via TTL natively,
    # so this only touches the in-memory fallback store.  One background task
    # per app instance; cancelled cleanly on shutdown.
    @app.on_event("startup")
    async def _start_idempotency_cleanup() -> None:
        from backend.middleware.idempotency_middleware import cleanup_expired_entries

        async def _hourly_cleanup() -> None:
            while True:
                try:
                    await asyncio.sleep(3600)
                    cleanup_expired_entries()
                except asyncio.CancelledError:
                    break
                except Exception:
                    logger.exception("Idempotency cleanup task failed")

        app.state._idempotency_cleanup_task = asyncio.create_task(_hourly_cleanup())

    @app.on_event("shutdown")
    async def _stop_idempotency_cleanup() -> None:
        task = getattr(app.state, "_idempotency_cleanup_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass  # Task already stopped — shutdown proceeds normally

    # ── FCM push sender (Gate-31) ────────────────────────────────────────
    # Constructed after the NotificationCenter so it can subscribe to the
    # alert-created/alert-resolved in-process subscriber list.  Graceful
    # no-op when OPERION_FIREBASE_CREDENTIALS is absent/unset (PushSender
    # logs a warning and stays disabled).  Never blocks startup.
    @app.on_event("startup")
    async def _start_fcm_push_sender() -> None:
        try:
            from backend.dependencies import init_db
            from services.operations.notification_center import NotificationCenter
            from services.operations.push_sender import PushSender

            db = init_db(app)
            nc = NotificationCenter(db=db)
            sender = PushSender(notification_center=nc, db=db)
            app.state.notification_center = nc
            app.state.push_sender = sender
        except Exception:
            logger.warning("FCM push sender startup skipped", exc_info=True)

    return app


app = create_app()

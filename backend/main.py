import logging
import os
from contextlib import asynccontextmanager
from typing import Dict, Optional

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
from backend.metrics import PrometheusMiddleware
from backend.middleware.auth_middleware import AuthMiddleware
from backend.middleware.correlation_middleware import CorrelationMiddleware
from backend.middleware.csrf import CSRFMiddleware
from backend.middleware.idempotency_middleware import IdempotencyMiddleware
from backend.middleware.logging_middleware import LoggingMiddleware
from backend.middleware.rate_limit_middleware import RateLimitMiddleware
from backend.middleware.security_headers_middleware import SecurityHeadersMiddleware
from backend.middleware.webhook_middleware import WebhookBodyMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application lifecycle — shutdown releases shared clients best-effort.

    In-flight requests are drained by the server (uvicorn/gunicorn handle
    SIGTERM natively); this hook closes shared resources (Redis client).
    """
    yield
    try:
        from backend.utils import rate_limit as _rl
        if _rl._redis_client is not None:
            _rl._redis_client.close()
    except Exception:
        pass
    logger.info("Operion API shutdown complete")


def create_app(settings: Optional[BackendSettings] = None) -> FastAPI:
    if settings is None:
        settings = BackendSettings()

    env_mode = os.environ.get("OPERION_ENV", "development")
    is_production = env_mode == "production"

    app = FastAPI(
        title="Operion ERP API",
        version="1.0.0",
        lifespan=lifespan,
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
        cors_kwargs["allow_origin_regex"] = r"http://(localhost|127\.0\.0\.1)(:\d+)?"
        cors_kwargs["allow_origins"] = []
    else:
        cors_kwargs["allow_origins"] = allowed_origins
        # Pages preview deployments (<hash>.operion-website.pages.dev)
        cors_kwargs["allow_origin_regex"] = r"https://([\w-]+\.)?operion-website\.pages\.dev"

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
    # CSRF (double-submit cookie) — placed after the rate limiter so flood
    # traffic is throttled before CSRF work, and before WebhookBodyMiddleware
    # because CSRF only inspects headers (the raw body is left untouched for
    # the webhook signature check that runs later in the stack).
    app.add_middleware(
        CSRFMiddleware,
        is_production=is_production,
    )
    app.add_middleware(WebhookBodyMiddleware)
    app.add_middleware(PrometheusMiddleware)

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
                     get_correlation_id(), request.method, request.url.path, exc, exc_info=True)

        return JSONResponse(status_code=status, content=problem.to_dict())

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        from backend.errors import ProblemDetail, get_error_code_for_exception

        error_code, status = get_error_code_for_exception(exc)
        problem = ProblemDetail(
            type=f"https://api.operionerp.xyz/errors/{error_code}",
            title="Internal server error",
            status=status,
            detail="An unexpected error occurred. Please try again later.",
            instance=str(request.url),
            error_code=error_code.value,
        )
        logger.error("500 error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(status_code=status, content=problem.to_dict())

    @app.get("/api/v1/version")
    def version_endpoint() -> Dict[str, str]:
        """Public version + environment info (deployment verification)."""
        return {
            "name": "operion-api",
            "version": app.version,
            "environment": env_mode,
        }

    app.include_router(api_v1_router)

    return app


app = create_app()

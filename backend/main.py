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
from backend.middleware.auth_middleware import AuthMiddleware

logger = logging.getLogger(__name__)


def create_app(settings: Optional[BackendSettings] = None) -> FastAPI:
    if settings is None:
        settings = BackendSettings()

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
        "http://localhost:8000,http://127.0.0.1:8000" if not is_production else "https://app.operionerp.xyz",
    ).split(",")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    )

    app.add_middleware(AuthMiddleware)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error. Please try again later."},
        )

    @app.exception_handler(500)
    async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("500 error on %s %s: %s", request.method, request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error."},
        )

    app.include_router(api_v1_router)

    return app


app = create_app()

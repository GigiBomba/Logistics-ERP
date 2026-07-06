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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.v1.router import api_v1_router
from backend.config import BackendSettings
from backend.middleware.auth_middleware import AuthMiddleware

def create_app(settings: Optional[BackendSettings] = None) -> FastAPI:
    if settings is None:
        settings = BackendSettings()

    app = FastAPI(
        title="Operion ERP API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(AuthMiddleware)

    app.include_router(api_v1_router)

    @app.on_event("startup")
    async def startup() -> None:
        # Choreographer — headless static image export
        try:
            from utils.chart_export import configure_choreographer_export
            configure_choreographer_export()
        except Exception:
            pass

    @app.on_event("shutdown")
    async def shutdown() -> None:
        pass

    return app


app = create_app()

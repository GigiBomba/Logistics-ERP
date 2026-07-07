import logging
from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class BackendSettings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────
    db_engine: str = "sqlite"
    db_path: str = "data/cashflow.db"
    postgres_dsn: Optional[str] = None

    # ── Redis / Celery ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = 3600
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # ── Server ────────────────────────────────────────────────────────────
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_workers: int = 4

    # ── JWT ───────────────────────────────────────────────────────────────
    jwt_secret_key: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15

    # ── Refresh token ─────────────────────────────────────────────────────
    refresh_token_expire_days: int = 7

    # ── bcrypt ─────────────────────────────────────────────────────────────
    bcrypt_rounds: int = 12

    # ── Admin gateway (bcrypt hash, never plaintext) ──────────────────────
    admin_email: str = ""
    admin_password_hash: str = ""

    model_config: Dict[str, Any] = {"env_prefix": "OPERION_"}

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._check_admin_config()

    def _check_admin_config(self) -> None:
        """Warn at startup if admin email is set but no password hash."""
        if self.admin_email and not self.admin_password_hash:
            logger.warning(
                "OPERION_ADMIN_EMAIL is set but OPERION_ADMIN_PASSWORD_HASH "
                "is empty — admin login will fail. Generate a hash with "
                "the one-time script and set OPERION_ADMIN_PASSWORD_HASH."
            )
        if not self.jwt_secret_key:
            logger.warning(
                "OPERION_JWT_SECRET_KEY is not set — JWT authentication "
                "will fail. Generate a key with: openssl rand -hex 32"
            )

import logging
import os
from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class BackendSettings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────
    db_engine: str = "sqlite"
    db_path: str = "data/cashflow.db"
    postgres_dsn: Optional[str] = None
    db_pool_min: int = 2
    db_pool_max: int = 20

    # ── Redis / Celery ────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""
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

    # ── Field-level encryption (used for SMTP passwords etc.) ─────────────
    encryption_key: str = ""

    # ── bcrypt ─────────────────────────────────────────────────────────────
    bcrypt_rounds: int = 12

    # ── Admin gateway (bcrypt hash, never plaintext) ──────────────────────
    admin_email: str = ""
    admin_password_hash: str = ""

    model_config = SettingsConfigDict(
        env_prefix="OPERION_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._check_admin_config()

    def _check_admin_config(self) -> None:
        """Validate critical security configuration at startup.

        Raises RuntimeError in production if mandatory settings are missing.
        """
        env = os.environ.get("OPERION_ENV", "development")

        # ── Admin email without password hash ──────────────────────────
        if self.admin_email and not self.admin_password_hash:
            logger.warning(
                "OPERION_ADMIN_EMAIL is set but OPERION_ADMIN_PASSWORD_HASH "
                "is empty — admin login will fail. Generate a hash with "
                "the one-time script and set OPERION_ADMIN_PASSWORD_HASH."
            )

        # ── JWT secret ─────────────────────────────────────────────────
        if not self.jwt_secret_key:
            msg = (
                "OPERION_JWT_SECRET_KEY is not set. JWT tokens cannot be "
                "signed or verified. Generate a key with: openssl rand -hex 32"
            )
            if env == "production":
                raise RuntimeError(msg)
            logger.warning(msg)

        # ── API key in production ──────────────────────────────────────
        if env == "production" and not os.environ.get("OPERION_API_KEY"):
            raise RuntimeError(
                "OPERION_API_KEY must be set in production. "
                "Without it, the API has no transport-layer authentication."
            )

        # ── Redis connectivity in production ───────────────────────────
        if env == "production" and self.redis_url:
            try:
                import redis as _redis
                r = _redis.Redis.from_url(self.redis_url, socket_timeout=3, password=self.redis_password or None)
                r.ping()
                r.close()
            except Exception as exc:
                logger.error(
                    "OPERION_REDIS_URL=%s — Redis is unreachable in production. "
                    "Rate limiting, refresh token storage, and caching will fail: %s",
                    self.redis_url, exc,
                )

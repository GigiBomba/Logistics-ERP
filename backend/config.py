import logging
import os
from typing import Any, Dict, Optional

from pydantic import AliasChoices, Field
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

    # ── Site (frontend) ──────────────────────────────────────────────────
    # Base URL of the public website — used to build emailed links
    # (password reset, invites). Env: OPERION_SITE_URL.
    site_url: str = "https://operionerp.xyz"

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

    # ── Cloudflare Turnstile ───────────────────────────────────────────────
    # Secret key used to verify Turnstile tokens server-side
    # (backend.services.turnstile). Both the canonical name and the
    # OPERION_-prefixed variant are accepted as env vars.
    turnstile_secret_key: Optional[str] = Field(
        None,
        validation_alias=AliasChoices(
            "TURNSTILE_SECRET_KEY",
            "OPERION_TURNSTILE_SECRET_KEY",
        ),
        description="Cloudflare Turnstile siteverify secret key.",
    )

    # ── MFA (TOTP) ───────────────────────────────────────────────────────
    # TTL (seconds) of the short-lived, single-use mid-login MFA session
    # token issued when a user with MFA enabled submits valid credentials.
    mfa_session_ttl_seconds: int = 300          # 5 minutes
    # TOTP verification window: ± this many 30-second steps around now.
    mfa_totp_window_steps: int = 1              # ±30s tolerance
    mfa_backup_codes_count: int = 10
    mfa_issuer: str = "Operion"
    # Server key used to XOR-encrypt mfa_secret at rest. When empty, falls
    # back to OPERION_JWT_SECRET_KEY. Never store TOTP secrets in plaintext.
    mfa_secret_encryption_key: str = ""

    # ── CSRF (double-submit cookie, defense-in-depth) ────────────────────
    csrf_cookie_name: str = "csrf_token"
    csrf_header_name: str = "X-CSRF-Token"
    csrf_cookie_max_age: int = 2592000          # 30 days
    # Extra path prefixes exempt from CSRF enforcement (defaults in the
    # middleware: /auth/token, /webhooks/*, /auth/mfa/verify,
    # /auth/mfa/backup-code). Requests without a browser Origin header are
    # always exempt (desktop/native ERP clients have no CSRF exposure).
    csrf_exempt_paths: list[str] = []

    # ── Stripe billing (per-truck subscriptions) ────────────────────────
    # Both the bare STRIPE_* names and the OPERION_-prefixed variants are
    # accepted (mirrors the Turnstile field pattern above). When the secret
    # keys are unset the billing endpoints deliberately fall back to clearly-
    # marked mock URLs and the Stripe webhook returns 501 — the API never
    # requires live keys to boot or to run tests.
    stripe_secret_key: Optional[str] = Field(
        None,
        validation_alias=AliasChoices(
            "STRIPE_SECRET_KEY",
            "OPERION_STRIPE_SECRET_KEY",
        ),
        description="Stripe secret (test or live) key. When unset, "
        "checkout/portal use clearly-marked mock fallbacks.",
    )
    stripe_webhook_secret: Optional[str] = Field(
        None,
        validation_alias=AliasChoices(
            "STRIPE_WEBHOOK_SECRET",
            "OPERION_STRIPE_WEBHOOK_SECRET",
        ),
        description="Stripe webhook signing secret. When unset, "
        "POST /webhooks/stripe returns 501 (never processes unverified).",
    )

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

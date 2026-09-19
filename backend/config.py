from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ── Process-global settings cache (F1) ──────────────────────────────────
# ``BackendSettings()`` parses ``.env`` + every OPERION_* env var through
# Pydantic on every construction — request hot paths (auth, mfa, admin,
# support, security dependencies) were instantiating it 4-5x per request.
# These settings are process-global by design (single-install deployment,
# no tenant data), so one cached instance per process is safe and correct.
_settings_cache: Optional["BackendSettings"] = None
_settings_fingerprint: Optional[str] = None
_settings_class: Optional[type] = None


def _env_fingerprint() -> str:
    """Cheap fingerprint of the env inputs that feed ``BackendSettings``.

    Hashes every ``OPERION_*`` env var plus the ``.env`` file mtime (when
    present).  This is a few microseconds on the hot path — orders of
    magnitude cheaper than re-parsing the whole settings object — and it
    makes the cache self-invalidating when tests (or an operator) mutate
    the environment between calls, without any explicit ``reload_settings``.
    """
    import hashlib

    h = hashlib.sha1()
    for key, value in sorted(os.environ.items()):
        if key.startswith("OPERION_"):
            h.update(key.encode("utf-8", "replace"))
            h.update(b"=")
            h.update(str(value).encode("utf-8", "replace"))
            h.update(b"\0")
    try:
        h.update(str(os.path.getmtime(".env")).encode("utf-8"))
    except OSError:
        pass
    return h.hexdigest()


def get_settings() -> "BackendSettings":
    """Return the process-global :class:`BackendSettings` instance.

    The first call parses ``.env`` and the environment once and caches
    the result; every subsequent call reuses that instance while the
    settings inputs are unchanged (env fingerprint + class identity —
    covers tests that patch ``BackendSettings`` or mutate ``OPERION_*``
    env vars between cases).  Explicit invalidation is available via
    :func:`reload_settings`.

    Prefer this over constructing ``BackendSettings()`` directly in
    request/route code.
    """
    global _settings_cache, _settings_fingerprint, _settings_class
    fingerprint = _env_fingerprint()
    if (
        _settings_cache is None
        or _settings_class is not BackendSettings
        or fingerprint != _settings_fingerprint
    ):
        _settings_cache = BackendSettings()
        _settings_fingerprint = fingerprint
        _settings_class = BackendSettings
    return _settings_cache


def reload_settings() -> "BackendSettings":
    """Invalidate the cached settings and re-parse them from the environment.

    Clears ``_settings_cache`` and immediately rebuilds it, returning the
    fresh instance.  Tests that mutate env vars between cases call this so
    the next :func:`get_settings` reflects the new values instead of a
    stale cached copy.
    """
    global _settings_cache
    _settings_cache = None
    return get_settings()


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

    # ── Local Download signed-URL tokens (blueprint §5.3) ────────────────
    # HMAC secret used to sign short-lived download tokens embedded in the
    # manifest's ``download_url``.  Falls back to ``jwt_secret_key`` when
    # left empty (single-secret deployments).
    local_download_token_secret: str = ""
    local_download_token_ttl_seconds: int = 900  # 15 minutes

    # ── Mobile Phase 2: generated export files (analytics/history exports) ─
    export_dir: str = "data/exports"

    # ── Mobile Phase 4: uploaded tachograph files (before async parse) ─────
    tacho_upload_dir: str = "data/tacho_uploads"

    # ── Refresh token ─────────────────────────────────────────────────────
    refresh_token_expire_days: int = 7
    # "Remember me" login → long-lived refresh cookie; session login → short.
    # Env: OPERION_REMEMBER_TOKEN_EXPIRE_DAYS / OPERION_SESSION_TOKEN_EXPIRE_DAYS.
    remember_token_expire_days: int = 30
    session_token_expire_days: int = 7

    # ── Field-level encryption (used for SMTP passwords etc.) ─────────────
    encryption_key: str = ""

    # ── MFA (TOTP two-factor) ──────────────────────────────────────────────
    # Issuer shown in the authenticator app label ("Operion:<email>").
    # Env: OPERION_MFA_ISSUER.
    mfa_issuer: str = "Operion"
    # TOTP acceptance window in steps (each step = 30s).  1 = current step
    # plus one step of clock skew either way.
    mfa_totp_window_steps: int = 1
    # Number of single-use recovery codes returned once at confirm time.
    mfa_backup_codes_count: int = 10
    # Optional dedicated key for encrypting TOTP secrets at rest; falls back
    # to jwt_secret_key when empty.  Env: OPERION_MFA_SECRET_ENCRYPTION_KEY.
    mfa_secret_encryption_key: str = ""

    # ── bcrypt ─────────────────────────────────────────────────────────────
    bcrypt_rounds: int = 12

    # ── Admin gateway (bcrypt hash, never plaintext) ──────────────────────
    admin_email: str = ""
    admin_password_hash: str = ""

    # ── operion-ops support-service proxy ─────────────────────────────────
    support_internal_auth: str = "dev-insecure-replace-in-production"
    support_service_url: str = "http://host.docker.internal:8100"

    # ── Stripe (billing, blueprint §4) ────────────────────────────────────
    # Env: OPERION_STRIPE_SECRET_KEY / OPERION_STRIPE_WEBHOOK_SECRET /
    # OPERION_STRIPE_PUBLISHABLE_KEY. Stripe is strictly env-gated: billing
    # endpoints degrade to mocks / empty lists when these are unset.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_publishable_key: str = ""

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

        # ── Support service internal auth ─────────────────────────────
        if not self.support_internal_auth or self.support_internal_auth == "dev-insecure-replace-in-production":
            msg = (
                "OPERION_SUPPORT_INTERNAL_AUTH is not set to a real secret. "
                "The support-service proxy has no internal auth. "
                "Generate a key with: openssl rand -hex 32"
            )
            if env == "production":
                raise RuntimeError(msg)
            logger.warning(msg)

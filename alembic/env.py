import os
import sys
from logging.config import fileConfig

from alembic import context

# ── Ensure the project root is on sys.path ──────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Alembic Config object ───────────────────────────────────────────────
config = context.config

# ── Logging ─────────────────────────────────────────────────────────────
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Metadata ────────────────────────────────────────────────────────────
# This project uses raw SQL (not SQLAlchemy ORM), so target_metadata is None.
target_metadata = None


# ── Database URL resolution ─────────────────────────────────────────────
def get_url() -> str:
    """Return the database connection URL based on the active engine.

    The engine is controlled by the ``OPERION_DB_ENGINE`` environment
    variable (defaults to ``"sqlite"``).
    """
    engine = os.environ.get("OPERION_DB_ENGINE", "sqlite")

    if engine == "postgresql":
        # Prefer the DSN from the project config, then env var, then fallback.
        try:
            from backend.config import BackendSettings

            settings = BackendSettings()
            if settings.postgres_dsn:
                return settings.postgres_dsn
        except Exception:
            pass

        pg_dsn = os.environ.get("OPERION_POSTGRES_DSN")
        if pg_dsn:
            return pg_dsn

        raise RuntimeError(
            "No PostgreSQL DSN configured. Set OPERION_POSTGRES_DSN environment variable "
            "or configure BackendSettings.postgres_dsn."
        )

    # SQLite: default path relative to project root
    return "sqlite:///./data/cashflow.db"


# ── Offline migration mode ──────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Configure context for offline (script-generation) mode."""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# ── Online migration mode ───────────────────────────────────────────────
def run_migrations_online() -> None:
    """Configure context for online (live-DB) mode."""
    from sqlalchemy import create_engine

    connectable = create_engine(get_url())

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


# ── Entry point ─────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

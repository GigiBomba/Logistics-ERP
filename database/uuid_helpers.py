"""UUID generation helpers for dual SQLite/PostgreSQL compatibility.

PostgreSQL uses ``gen_random_uuid()`` natively.  SQLite has no built-in
UUID generation, so we supply the value from Python for INSERT statements.

Usage in repository create() methods::

    from database.uuid_helpers import new_uuid
    data["id"] = new_uuid(db)
"""
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from database.db_manager import DatabaseManager


def new_uuid(db: "DatabaseManager") -> str:
    """Return a new UUID string suitable for either database engine.

    For PostgreSQL the ``gen_random_uuid()`` default in the schema handles it.
    For SQLite we supply the value explicitly.
    """
    return str(uuid.uuid4())


def is_postgresql(db: "DatabaseManager") -> bool:
    """Check whether the active database engine is PostgreSQL."""
    return getattr(db, "_engine", "sqlite") == "postgresql"

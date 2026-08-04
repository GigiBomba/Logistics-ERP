"""Thread-safe tenant context provider.

Replaces mutable ``user_company_id`` / ``user_role`` attributes on the
shared ``DatabaseManager`` singleton with proper ``contextvars.ContextVar``
based context.  This guarantees that concurrent async requests cannot
influence each other's tenant filters.

Usage (backend — set per-request in auth middleware)::

    from database.tenant_context import set_request_context

    set_request_context(company_id=5, role="dispatcher")

Usage (Celery task — set before any DB access)::

    from database.tenant_context import set_company_context

    set_company_context(company_id=5)

Usage (desktop — set once after login)::

    from database.tenant_context import set_request_context

    set_request_context(company_id=1, role="admin")

Reading context (repositories and services)::

    from database.tenant_context import get_company_id, get_scoped

    if get_scoped():
        company_id = get_company_id()
"""

from __future__ import annotations

import contextvars
from typing import Optional

__all__ = [
    "set_company_context",
    "set_user_role",
    "set_request_context",
    "get_company_id",
    "get_user_role",
    "get_scoped",
    "clear_context",
]

_company_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "tenant_company_id", default=None,
)
_user_role: contextvars.ContextVar[str] = contextvars.ContextVar(
    "tenant_user_role", default="",
)


def set_company_context(company_id: Optional[int]) -> None:
    """Set the current execution context's company ID.

    Intended for background tasks (Celery workers) where only the
    company_id is known and the user role defaults to empty (admin
    scope).

    Pass ``None`` to clear the company scope (admin / cross-tenant).
    """
    _company_id.set(company_id)


def set_user_role(role: str) -> None:
    """Set the current execution context's user role."""
    _user_role.set(role)


def set_request_context(company_id: Optional[int], role: str = "") -> None:
    """Set both company ID and user role for an authenticated request.

    Typical usage from FastAPI middleware after JWT validation::

        set_request_context(
            company_id=payload.get("company_id"),
            role=payload.get("role", ""),
        )
    """
    _company_id.set(company_id)
    _user_role.set(role)


def get_company_id() -> Optional[int]:
    """Return the current execution context's company ID, or ``None``."""
    return _company_id.get()


def get_user_role() -> str:
    """Return the current execution context's user role."""
    return _user_role.get()


def get_scoped() -> bool:
    """Return ``True`` if the current context is tenant-scoped.

    A context is scoped when:
    * a company_id is set (not ``None``), AND
    * the user role is NOT ``"admin"`` (admins see all tenants).

    When this returns ``False``, repositories should skip the
    ``company_id`` filter so the caller sees data across all tenants.
    """
    cid = _company_id.get()
    role = _user_role.get()
    return cid is not None and role != "admin"


def clear_context() -> None:
    """Reset tenant context to defaults (no company, no role).

    Useful in test teardown or after processing a unit of work
    in a background task.
    """
    _company_id.set(None)
    _user_role.set("")

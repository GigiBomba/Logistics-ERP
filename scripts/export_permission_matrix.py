"""Export the real PermissionService decision matrix to shared/test_vectors.

Introspects the REAL ``services.permission_service.PermissionService``:

  - roles         → the class's ``ROLE_*`` string constants
  - permissions   → every public ``can_*`` method (via ``inspect.getmembers``)

For every (role, permission) pair the real decision logic is executed and the
resulting ``expected_allowed`` value is recorded — the matrix is derived from
the code, never hand-written.

The ONLY stub is the user lookup: every ``can_*`` method resolves the acting
user via ``PermissionService._get_user(user_id)`` → ``UserRepository(db)
.get_by_id(user_id)``.  That single lookup is replaced with a mock user dict;
all role checks, the ``is_authenticated`` gate and denial reasons run the real
code.  ``is_active: True`` is required because ``is_authenticated`` rejects
inactive users (``user.get("is_active", False)``).

Run:  python scripts/export_permission_matrix.py
Writes: shared/test_vectors/permission_matrix.json
"""
from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path

# Ensure the project root is on sys.path so repo modules are importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from services.permission_service import PermissionService

OUT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "shared",
    "test_vectors",
    "permission_matrix.json",
)

ROLES = [
    PermissionService.ROLE_ADMIN,
    PermissionService.ROLE_MANAGER,
    PermissionService.ROLE_DISPATCHER,
    PermissionService.ROLE_DRIVER,
]


def _collect_permissions() -> list[str]:
    """Return the sorted names of all public ``can_*`` methods."""
    return sorted(
        name
        for name, member in inspect.getmembers(PermissionService, predicate=inspect.isfunction)
        if name.startswith("can_")
    )


def _evaluate(role: str, permission: str) -> bool:
    """Execute the real decision logic for *permission* as *role*.

    Stubs ONLY ``PermissionService._get_user`` (the DB/repository lookup) with
    a mock user dict for the role; everything else is the real code.
    """
    mock_user = {"id": 1, "role": role, "company_id": 1, "is_active": True}
    svc = PermissionService(db=None)
    svc._get_user = lambda user_id: mock_user  # type: ignore[method-assign]
    result = getattr(svc, permission)(user_id=1)
    return bool(result.allowed)


def main() -> None:
    permissions = _collect_permissions()
    matrix: list[dict[str, object]] = []
    for role in ROLES:
        for permission in permissions:
            matrix.append(
                {
                    "role": role,
                    "permission": permission,
                    "expected_allowed": _evaluate(role, permission),
                }
            )

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(matrix, fh, indent=2)
        fh.write("\n")

    allowed = sum(1 for row in matrix if row["expected_allowed"])
    print(
        f"Wrote {len(matrix)} (role, permission) pairs to {OUT_PATH} "
        f"({len(permissions)} permissions x {len(ROLES)} roles; "
        f"{allowed} allowed / {len(matrix) - allowed} denied)"
    )


if __name__ == "__main__":
    main()

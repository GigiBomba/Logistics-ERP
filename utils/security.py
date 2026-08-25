"""Shared password-hashing helper (bcrypt).

The desktop app is local-first (Phase F) and the packaged client ships NO
``backend`` package.  ``services/user_service.py`` (the Team view) needs
``hash_password``, so the implementation lives HERE — a non-backend module —
instead of in ``backend/security.py``.

``backend/security.py`` re-exports it for server-side compatibility, so the
two sides can never drift.

NOTE: the desktop app is not the server; hashing is only performed when the
admin creates/resets a user password from the Team view.  The default bcrypt
rounds mirror ``BackendSettings().bcrypt_rounds`` (env ``OPERION_BCRYPT_ROUNDS``,
default 12) so hashes produced on the desktop are interoperable with the
server's.
"""
from __future__ import annotations

import os
from typing import Optional

import bcrypt

_DEFAULT_ROUNDS = 12


def _default_rounds() -> int:
    """Resolve the bcrypt cost factor (env override, mirroring BackendSettings)."""
    try:
        return int(os.environ.get("OPERION_BCRYPT_ROUNDS", str(_DEFAULT_ROUNDS)))
    except (TypeError, ValueError):
        return _DEFAULT_ROUNDS


def hash_password(password: str, rounds: Optional[int] = None) -> str:
    """Return a salted bcrypt hash of *password*.

    Note: bcrypt has a 72-byte input limit.  We truncate to 72 bytes to
    match the behavior of ``verify_password`` in ``backend/security.py``.
    """
    if rounds is None:
        rounds = _default_rounds()
    return bcrypt.hashpw(
        password.encode("utf-8")[:72],
        bcrypt.gensalt(rounds=rounds),
    ).decode("utf-8")

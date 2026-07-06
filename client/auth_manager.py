"""Singleton auth state manager for the PySide6 desktop client.

Usage::

    from client.auth_manager import get_auth, set_auth, is_admin

    # Boot-time hydration (auto-login from persisted storage)
    if not hydrate_from_storage():
        # No valid stored session — app starts without admin access
        ...

    # Show login dialog on demand:
    if require_admin_async(self):
        # admin tab can be injected
        ...
"""

import logging
from typing import Optional

from client.auth import Auth

logger = logging.getLogger(__name__)

_auth_instance: Optional[Auth] = None


def get_auth() -> Optional[Auth]:
    """Return the global ``Auth`` singleton (or ``None`` if not logged in)."""
    global _auth_instance
    return _auth_instance


def set_auth(auth: Auth) -> None:
    """Set the global ``Auth`` singleton."""
    global _auth_instance
    _auth_instance = auth


def clear_auth() -> None:
    """Clear the global ``Auth`` singleton and any stored token."""
    global _auth_instance
    if _auth_instance is not None:
        _auth_instance.clear_token()
    _auth_instance = None


def is_admin() -> bool:
    """Convenience check — shortcut for ``get_auth() and get_auth().is_admin``."""
    auth = get_auth()
    if auth is None:
        return False
    return auth.is_admin


def hydrate_from_storage() -> bool:
    """Hydrate the global ``Auth`` singleton from persisted storage.

    Called once at application boot **after** the ``QApplication``
    instance exists.  Reads stored credentials from ``QSettings``,
    validates expiry, and silently restores the session if valid.

    Returns:
        ``True`` if a valid, unexpired session was restored from storage.
        ``False`` if no stored credentials exist or the stored token
        has expired.
    """
    global _auth_instance
    auth = Auth.load_from_storage()
    if auth.is_authenticated and not auth.token_expired:
        _auth_instance = auth
        logger.info(
            "Auto-login: restored admin session from persistent storage."
        )
        return True
    if auth.is_authenticated:
        logger.info(
            "Auto-login: stored token expired — clearing."
        )
        auth._clear_stored_tokens()
        _auth_instance = None
    return False


def require_admin_async(parent: object = None) -> bool:
    """Prompt the user to authenticate as admin if not already logged in.

    Args:
        parent: A ``QWidget`` to use as the parent of the modal login dialog.
                Can be ``None`` (the dialog will have no transient parent).

    Returns:
        ``True`` if an admin session was established (either already present
        or after successful login).
        ``False`` if the user cancelled the dialog or login failed.
    """
    if is_admin():
        return True

    # Lazy import — avoid PySide6 dependency at module level
    try:
        from ui.dialogs.login_dialog import QtLoginDialog  # type: ignore[import-untyped]
    except ImportError:
        logger.error(
            "Cannot import QtLoginDialog — PySide6 may not be available."
        )
        return False

    try:
        dlg = QtLoginDialog(parent)  # type: ignore[arg-type]
        result = dlg.exec()
        if result == 1:  # QDialog.Accepted
            return is_admin()
        return False
    except Exception as exc:
        logger.exception("Login dialog failed: %s", exc)
        return False

"""Test helpers for API tests.

Import ``create_test_app`` instead of ``backend.main.create_app`` so that
auth dependencies are automatically overridden for all endpoints.
"""
from __future__ import annotations

# Mock user for auth overrides
MOCK_USER = {"id": 1, "email": "test@test.com", "role": "admin", "is_admin": True, "company_id": 1}


def create_test_app(**kwargs):
    """Create a real backend app with auth dependencies overridden.

    Use this instead of ``backend.main.create_app()`` in test fixtures so
    that endpoints requiring JWT auth work without real tokens.
    """
    from backend.main import create_app
    from backend.dependencies_security import (
        get_current_user,
        require_dispatcher,
        require_admin,
        require_manager,
    )

    app = create_app(**kwargs)
    app.dependency_overrides[get_current_user] = lambda: MOCK_USER
    app.dependency_overrides[require_dispatcher] = lambda: MOCK_USER
    app.dependency_overrides[require_admin] = lambda: MOCK_USER
    app.dependency_overrides[require_manager] = lambda: MOCK_USER
    return app


def create_real_app(**kwargs):
    """Create a real backend app WITHOUT auth overrides.

    Use this for tests that need to verify real JWT auth flows.
    """
    from backend.main import create_app
    return create_app(**kwargs)
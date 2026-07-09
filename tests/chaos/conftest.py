"""Shared fixtures for chaos tests — reuses the security test suite's app fixture.

The security conftest sets up a temporary SQLite database, seeds test data
(companies, users, trips, clients, drivers, trucks), and provides session-scoped
``app`` and ``client`` fixtures plus per-function auth header fixtures
(``auth_admin``, ``auth_a``, ``auth_b``).

All chaos tests below reuse those fixtures so they don't repeat the
expensive setup.
"""

import os

# Ensure the JWT secret is set before any test module imports backend modules.
# The security conftest's session-scoped ``app`` fixture also sets this,
# but some chaos tests (e.g. clock skew) call create_access_token directly
# before any fixture runs, so we need it at module-import time.
os.environ.setdefault(
    "OPERION_JWT_SECRET_KEY",
    "test-secret-key-32-chars-for-testing-only!!",
)

# Point to the security test suite's conftest for the app/client fixtures
from tests.security.conftest import (  # noqa: F401, E402
    app, client, tokens, admin_token, auth_admin, auth_a, auth_b,
)

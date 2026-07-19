# Integration Tests — PostgreSQL Backend

This directory contains **integration tests** that exercise the application's
backend services against a real PostgreSQL database (via ``psycopg2``) and
optionally against Redis.

---

## Prerequisites

1. **Docker Desktop** (or Docker Engine + Docker Compose v2).
2. **Python 3.9+** with the project's dependencies installed:
   ```bash
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```
3. **Ports 5432 (PostgreSQL) and 6379 (Redis) free** on the host — the test
   services bind to these ports by default.

---

## Quick Start

### 1. Start test infrastructure

```bash
docker compose -f docker-compose.test.yml up -d
```

This starts:
- **PostgreSQL 16** on port ``5432`` (database ``operion_test``, user ``operion``,
  password ``operion_test``).
- **Redis 7** on port ``6379`` (no password).

Both services include health checks.  The command waits until they report
healthy before returning.

### 2. Run integration tests

```bash
# All integration tests:
pytest tests/integration/ -v -m integration

# A specific test file:
pytest tests/integration/test_trip_workflow.py -v --tb=long

# With live PostgreSQL (override the default DSN):
OPERION_TEST_POSTGRES_DSN="postgresql://user:pass@localhost:5432/mydb" \
  pytest tests/integration/ -v -m integration

# With parallel execution:
pytest tests/integration/ -v -n auto -m integration
```

### 3. Stop infrastructure

```bash
docker compose -f docker-compose.test.yml down
```

To also delete the persistent volumes:

```bash
docker compose -f docker-compose.test.yml down -v
```

---

## Test Patterns and Conventions

### Fixture hierarchy

The fixtures in ``conftest.py`` are stacked as follows:

```
db_url          (session)   — DSN string, from env or default
  └─ pg_database   (session) — creates the database once
       └─ pg_migrations (session) — runs alembic upgrade → head
            └─ pg_session   (session) — persistent connection
                 └─ pg_db (autouse, function) — SAVEPOINT / ROLLBACK
```

### ``pg_db`` — your primary fixture

Every test in the ``tests/integration/`` directory automatically gets the
``pg_db`` fixture (it is ``autouse=True``).  This fixture:

1. Starts a **savepoint** (``SAVEPOINT test_sp``) before the test.
2. Yields the raw ``psycopg2`` connection (with ``RealDictCursor``).
3. Rolls back to the savepoint after the test finishes — **no data persists**
   between tests.

Because ``pg_db`` is auto-used, you **do not** need to request it explicitly
unless your test needs direct database access:

```python
import pytest
from repositories.trip_repository import TripRepository

@pytest.mark.integration
def test_trip_count(pg_db):
    repo = TripRepository(pg_db)
    assert repo.count() == 0
```

### Factory-based test data

Use the factory fixtures to build model instances with sensible defaults.
These are thin wrappers around the functions in
``tests/test_data/factories.py``:

```python
@pytest.mark.integration
def test_create_trip(pg_db, make_trip):
    trip = make_trip(client_id=42, reference="CUST-001")
    # trip is a TripCreate instance — pass it to a repository
```

Available factory fixtures:
- ``make_trip`` → ``TripCreate``
- ``make_client`` → ``ClientCreate``
- ``make_driver`` → ``DriverCreate``
- ``make_user`` → ``UserCreateRequest``
- ``make_vehicle`` → ``VehicleCreate``
- ``make_invoice`` → ``InvoiceCreate``

### Seeded test data

For tests that need a minimal set of related records (company, user, client,
truck, driver), inject the ``test_data`` fixture:

```python
@pytest.mark.integration
def test_assign_driver(pg_db, test_data):
    driver_id = test_data["driver_id"]
    truck_id = test_data["truck_id"]
    # … your test that needs real IDs …
```

``test_data`` returns a dictionary with keys: ``company_id``, ``user_id``,
``client_id``, ``truck_id``, ``driver_id``.

### Markers

Always mark integration tests with ``@pytest.mark.integration``:

```python
@pytest.mark.integration
def test_my_feature():
    ...
```

This lets the CI workflow selectively run (or skip) integration tests:
- **Linux runners**: run the full suite including integration tests.
- **Windows/macOS runners**: skip integration tests with
  ``-k "not integration"``.

Other relevant markers already defined in ``pyproject.toml``:
- ``e2e`` — end-to-end workflow tests
- ``slow`` — slow tests (deselect with ``-m "not slow"``)

### Auto-rollback and test isolation

Because ``pg_db`` rolls back after every test, you never need to clean up
inserted rows.  This also means:

- **Do not** commit inside a test — the rollback will discard your data.
- If you must commit (e.g., testing a feature that reads its own writes),
  use ``pg_session`` directly and manually manage transactions.

### Skipping tests when PostgreSQL is unavailable

If no PostgreSQL server is reachable at the DSN, the session-scoped
``pg_database`` fixture calls ``pytest.skip()``, which causes every test
that depends on it to be skipped with a clear message.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| ``OPERION_TEST_POSTGRES_DSN`` | ``postgresql://operion:operion_test@localhost:5432/operion_test`` | Test database DSN |
| ``OPERION_DB_ENGINE`` | ``sqlite`` (in CI) | Set to ``postgresql`` for integration tests |
| ``OPERION_JWT_SECRET_KEY`` | ``test-jwt-secret-key-for-testing`` (from root conftest) | JWT signing key |

---

## CI Integration

The workflow at ``.github/workflows/test-python.yml``:

1. Starts ``docker compose -f docker-compose.test.yml up -d`` on Linux.
2. Sets ``OPERION_DB_ENGINE=postgresql`` and ``OPERION_TEST_POSTGRES_DSN``.
3. Runs the full test suite with test sharding (``pytest-split``).

On Windows and macOS, integration tests are excluded because those runners
do not have Docker available by default.

---

## Troubleshooting

**"psycopg2 is not installed"**
```bash
pip install psycopg2-binary
```

**"PostgreSQL is not available — skipping integration tests"**
- Ensure the Docker containers are running: ``docker compose -f docker-compose.test.yml ps``
- Check ports: ``docker compose -f docker-compose.test.yml logs postgres-test``

**"database 'operion_test' already exists"**
- This is safe — the fixture uses ``CREATE DATABASE IF NOT EXISTS``.
- If the database is in a bad state, tear it down:
  ```bash
  docker compose -f docker-compose.test.yml down -v
  docker compose -f docker-compose.test.yml up -d
  ```

**"relation 'trips' does not exist"**
- Migrations have not been applied.  Check that ``alembic upgrade head`` runs
  successfully against the test database.  The ``pg_migrations`` fixture does
  this automatically; look for errors in the test session log.

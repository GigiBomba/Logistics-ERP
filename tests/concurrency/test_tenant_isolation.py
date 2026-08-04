"""Tenant isolation concurrency tests.

These tests prove that tenant context (``company_id`` / ``role``) is
properly isolated across threads and async tasks after the Phase A
refactor — i.e. that ``database.tenant_context`` (``contextvars``)
reliably replaces the old mutable-singleton-attribute pattern.

All tests use a **file-based** SQLite database so that each thread
gets its own ``sqlite3.Connection`` to the same backing file via
``DatabaseManager`` / ``ConnectionPool`` (WAL mode).
"""

from __future__ import annotations

import asyncio
import os
import queue
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

import pytest

from database.db_manager import DatabaseManager
from database.tenant_context import (
    clear_context,
    get_company_id,
    get_scoped,
    set_company_context,
    set_request_context,
)
from repositories.trip_repository import TripRepository

pytestmark = pytest.mark.concurrency


# ── Helpers ─────────────────────────────────────────────────────────────────


def _make_db() -> DatabaseManager:
    """Create a temporary file-based DatabaseManager.

    Seeds a ``companies`` row so that FK constraints on ``company_id``
    (added via ``ALTER TABLE ... REFERENCES companies(id)``) do not
    fail when inserting business objects.

    Caller MUST call ``_close_db(db)`` after use.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name
    tmp.close()
    db = DatabaseManager(path)
    # Seed the companies table (needed for FK constraints on company_id
    # columns added by _run_column_migrations).
    _seed_companies(db)
    return db


def _seed_companies(db: DatabaseManager) -> None:
    """Insert a range of company IDs so FK constraints don't block inserts."""
    for cid in range(0, 101):  # companies 0-100
        try:
            db.conn.execute(
                "INSERT OR IGNORE INTO companies (id, company_name, subscription_tier) "
                "VALUES (?, ?, 'starter')",
                (cid, f"Company-{cid}"),
            )
        except Exception:
            pass
    db.conn.commit()


def _close_db(db: DatabaseManager) -> None:
    """Close *db* and remove its backing files."""
    path = getattr(db, "_pool", None)
    db_path = ""
    if path and hasattr(path, "_db_path"):
        db_path = path._db_path
    db.close()
    if db_path:
        try:
            os.unlink(db_path)
        except Exception:
            pass
        for ext in ("-wal", "-shm"):
            try:
                os.unlink(db_path + ext)
            except Exception:
                pass


def _sample_trip(company_id: int, **overrides: Any) -> dict:
    """Return a minimal trip data dict."""
    data = {
        "created_at": "2026-07-01T00:00:00",
        "status": "Planned",
        "client_name": f"Client-C{company_id}",
        "truck_number": f"TRUCK-C{company_id}",
        "driver_name": f"Driver-C{company_id}",
        "distance_km": 100.0,
        "total_price_eur": 1000.0,
        "company_id": company_id,
    }
    data.update(overrides)
    return data


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_tenant_context():
    """Every test starts with a clean tenant context."""
    clear_context()
    yield
    clear_context()


# ── Tests ───────────────────────────────────────────────────────────────────


class TestThreadLocalIsolation:
    """Each thread's tenant context must be independent."""

    def test_context_is_independent_per_thread(self):
        """Two threads set different company_ids; each reads its own.

        This validates that ``contextvars.ContextVar`` (used by
        ``database.tenant_context``) correctly isolates per-thread
        state even when threads share the same ``DatabaseManager``
        singleton pattern.
        """
        results: Dict[str, Optional[int]] = {}
        barrier = threading.Barrier(2, timeout=10)

        def _worker(label: str, company_id: int) -> None:
            set_request_context(company_id, "dispatcher")
            barrier.wait(timeout=10)  # sync: both threads set context
            barrier.wait(timeout=10)  # sync: both threads read
            results[label] = get_company_id()

        t1 = threading.Thread(target=_worker, args=("A", 10))
        t2 = threading.Thread(target=_worker, args=("B", 20))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        assert results.get("A") == 10, f"Thread A saw {results.get('A')}, expected 10"
        assert results.get("B") == 20, f"Thread B saw {results.get('B')}, expected 20"

    def test_clear_context_does_not_affect_other_threads(self):
        """clear_context() in one thread must not clear another thread's context."""
        results: Dict[str, Optional[int]] = {}
        barrier_a = threading.Barrier(2, timeout=10)
        barrier_b = threading.Barrier(2, timeout=10)

        def _worker_a() -> None:
            set_request_context(100, "admin")
            barrier_a.wait()  # 1: A has set context
            barrier_b.wait()  # 2: B has set its context
            results["A_before"] = get_company_id()
            clear_context()
            results["A_after"] = get_company_id()
            barrier_a.wait()  # 3: sync before join

        def _worker_b() -> None:
            barrier_a.wait()  # 1: wait for A to set
            set_request_context(200, "dispatcher")
            barrier_b.wait()  # 2: B has set its context
            results["B"] = get_company_id()
            barrier_a.wait()  # 3: sync before join

        t1 = threading.Thread(target=_worker_a)
        t2 = threading.Thread(target=_worker_b)
        t1.start()
        t2.start()
        t1.join(timeout=10)
        t2.join(timeout=10)

        assert results["A_before"] == 100
        assert results["A_after"] is None
        assert results["B"] == 200  # B's context unaffected by A's clear_context()


class TestConcurrentTenantInserts:
    """Multiple threads insert trips for different companies concurrently."""

    def test_inserts_do_not_leak_across_companies(self):
        """Two threads insert 50 trips each for different companies.
        After both complete, verify each company sees only its own data.
        """
        db = _make_db()
        try:
            # Create companies in DB (needed for FK if trips have company FK)
            # Trips don't have a direct FK to companies, but company_id column exists
            n_per_company = 50

            def _insert_worker(company_id: int, results: list) -> None:
                """Insert *n_per_company* trips for *company_id*."""
                set_request_context(company_id, "dispatcher")
                repo = TripRepository(db)
                for i in range(n_per_company):
                    tid = repo.create(_sample_trip(company_id, truck_number=f"T-{company_id}-{i}"))
                    results.append(tid)

            results_a: list = []
            results_b: list = []

            t1 = threading.Thread(target=_insert_worker, args=(10, results_a))
            t2 = threading.Thread(target=_insert_worker, args=(20, results_b))

            t1.start()
            t2.start()
            t1.join(timeout=30)
            t2.join(timeout=30)

            # Now verify isolation by reading with each company's scope
            set_request_context(10, "dispatcher")
            repo = TripRepository(db)
            trips_for_10 = repo.get_all(limit=1000)
            assert len(trips_for_10) == n_per_company, (
                f"Company 10 saw {len(trips_for_10)} trips, expected {n_per_company}"
            )
            for t in trips_for_10:
                assert t.get("company_id") == 10, (
                    f"Trip {t['id']} has company_id={t.get('company_id')}, expected 10"
                )

            set_request_context(20, "dispatcher")
            trips_for_20 = repo.get_all(limit=1000)
            assert len(trips_for_20) == n_per_company, (
                f"Company 20 saw {len(trips_for_20)} trips, expected {n_per_company}"
            )
            for t in trips_for_20:
                assert t.get("company_id") == 20, (
                    f"Trip {t['id']} has company_id={t.get('company_id')}, expected 20"
                )

        finally:
            _close_db(db)

    def test_thread_pool_tenants_are_isolated(self):
        """Submit 10 parallel tasks with distinct company_ids via
        ``ThreadPoolExecutor``.  After all complete, verify that the
        database contains correct company_id on every row AND that
        reading back with each scope returns exactly the right rows.
        """
        db = _make_db()
        n_companies = 10
        rows_per_company = 20

        try:
            with ThreadPoolExecutor(max_workers=n_companies) as pool:

                def _insert(company_id: int) -> int:
                    """Insert *rows_per_company* trips and return count."""
                    set_request_context(company_id, "dispatcher")
                    repo = TripRepository(db)
                    inserted = 0
                    for i in range(rows_per_company):
                        repo.create(
                            _sample_trip(company_id, truck_number=f"TP-{company_id}-{i}")
                        )
                        inserted += 1
                    return inserted

                futures = {
                    pool.submit(_insert, cid): cid for cid in range(1, n_companies + 1)
                }

                total = 0
                for future in as_completed(futures):
                    total += future.result()

                assert total == n_companies * rows_per_company, (
                    f"Inserted {total}, expected {n_companies * rows_per_company}"
                )

            # Post-condition: each company should see exactly its own rows
            for cid in range(1, n_companies + 1):
                set_request_context(cid, "dispatcher")
                repo = TripRepository(db)
                rows = repo.get_all(limit=rows_per_company + 5)
                assert len(rows) == rows_per_company, (
                    f"Company {cid} sees {len(rows)} trips, expected {rows_per_company}"
                )
                for r in rows:
                    assert r["company_id"] == cid, (
                        f"Row {r['id']} has company_id={r['company_id']}, expected {cid}"
                    )

        finally:
            _close_db(db)


class TestContextVarPropagation:
    """Verify that ``contextvars`` propagate correctly through sync code paths
    used by FastAPI (sync ``def`` endpoints)."""

    def test_sub_thread_inherits_context(self):
        """A thread spawned after ``set_request_context`` should NOT inherit
        the parent's context — ``contextvars`` are per-thread, not inherited
        by default (unlike ``threading.local``).  This is the CORRECT
        behaviour: each thread must explicitly set its own context.
        """
        set_request_context(99, "admin")

        result_queue: queue.Queue = queue.Queue()

        def _child() -> None:
            # contextvars do NOT propagate to new threads by default
            result_queue.put(get_company_id())

        t = threading.Thread(target=_child)
        t.start()
        t.join(timeout=5)

        # Child should see None (default) because it didn't set its own context
        child_result = result_queue.get(timeout=1)
        assert child_result is None, (
            f"Child thread saw {child_result}, expected None "
            "(contextvars do not leak to spawned threads)"
        )
        # Parent should still see its context
        assert get_company_id() == 99


class TestAdminBypass:
    """Admin users (role='admin') must bypass company filtering."""

    def test_admin_sees_all_companies(self):
        """An admin-scoped repository should return all rows regardless of company_id."""
        db = _make_db()
        try:
            # Insert trips for two different companies as scoped user
            set_request_context(1, "dispatcher")
            repo = TripRepository(db)
            repo.create(_sample_trip(1))
            set_request_context(2, "dispatcher")
            repo.create(_sample_trip(2))

            # Now read as admin (no company scope)
            set_request_context(None, "admin")
            all_trips = repo.get_all(limit=100)
            assert len(all_trips) == 2, (
                f"Admin saw {len(all_trips)} trips, expected 2 (all companies)"
            )

            # Verify scoped user still sees only their own
            set_request_context(1, "dispatcher")
            trips_for_1 = repo.get_all(limit=100)
            assert len(trips_for_1) == 1

            set_request_context(2, "dispatcher")
            trips_for_2 = repo.get_all(limit=100)
            assert len(trips_for_2) == 1

        finally:
            _close_db(db)


class TestContextCleanup:
    """contextvars must be properly reset between units of work."""

    def test_clear_context_resets_to_defaults(self):
        set_request_context(42, "manager")
        assert get_company_id() == 42
        assert get_scoped() is True

        clear_context()

        assert get_company_id() is None
        assert get_scoped() is False

    def test_successive_set_request_context_overwrites(self):
        """Setting a new request context must completely replace the previous one."""
        set_request_context(10, "dispatcher")
        assert get_company_id() == 10

        set_request_context(20, "dispatcher")
        assert get_company_id() == 20

        set_request_context(30, "admin")
        assert get_company_id() == 30
        assert get_scoped() is False  # admin is never scoped

    def test_trip_context_cleanup_between_operations(self):
        """Simulate processing two back-to-back requests for different companies.
        After each, clear_context() resets state so the next starts clean.
        """
        db = _make_db()
        try:
            # Request 1: company 5 creates a trip
            set_request_context(5, "dispatcher")
            repo = TripRepository(db)
            repo.create(_sample_trip(5))
            clear_context()

            # Request 2: company 7 creates a trip (should NOT see company 5's data)
            set_request_context(7, "dispatcher")
            repo.create(_sample_trip(7))
            trips = repo.get_all(limit=100)
            assert len(trips) == 1
            assert trips[0]["company_id"] == 7

        finally:
            _close_db(db)


class TestAsyncIsolation:
    """Tenant isolation under asyncio — the production concurrency model.

    FastAPI handles requests on an asyncio event loop.  ``contextvars``
    are task-local in asyncio, meaning concurrent ``async def`` handlers
    automatically get independent context.  These tests verify that
    invariant explicitly.
    """

    @pytest.mark.asyncio
    async def test_async_tasks_have_independent_context(self):
        """Two concurrent asyncio tasks set different company_ids.

        Each task asserts its own context is independent of the other.
        """
        loop = asyncio.get_running_loop()

        async def _task(label: str, company_id: int) -> int:
            set_request_context(company_id, "dispatcher")
            # Yield control so the other task can run concurrently
            await asyncio.sleep(0)
            seen = get_company_id()
            return seen

        results = await asyncio.gather(
            _task("A", 10),
            _task("B", 20),
        )

        assert results[0] == 10
        assert results[1] == 20

    @pytest.mark.asyncio
    async def test_create_task_inherits_correct_context(self):
        """A child task created via ``asyncio.create_task`` inherits
        the parent's ``ContextVar`` value at the moment of creation.
        """
        set_request_context(42, "dispatcher")

        async def _child() -> int:
            return get_company_id()

        task = asyncio.create_task(_child())
        child_result = await task

        assert child_result == 42

    @pytest.mark.asyncio
    async def test_child_context_change_does_not_affect_parent(self):
        """Changing the context in a child task must not affect the parent."""
        set_request_context(1, "dispatcher")

        parent_before = get_company_id()

        async def _child() -> None:
            set_request_context(99, "admin")

        await asyncio.create_task(_child())

        parent_after = get_company_id()
        assert parent_before == 1
        assert parent_after == 1  # unchanged by child

    @pytest.mark.asyncio
    async def test_concurrent_scope_isolation(self):
        """Simulate two concurrent FastAPI requests with different JWT
        claims.  Each task sets its own context, queries the DB, and
        must see only the data belonging to its company.
        """
        db = _make_db()
        try:
            # Seed trips for two companies
            set_request_context(10, "dispatcher")
            repo = TripRepository(db)
            repo.create(_sample_trip(10, client_name="C10-Trip"))
            set_request_context(20, "dispatcher")
            repo.create(_sample_trip(20, client_name="C20-Trip"))
            clear_context()

            async def _query(company_id: int, expected_name: str) -> dict:
                """Simulate a FastAPI request handler."""
                set_request_context(company_id, "dispatcher")
                repo = TripRepository(db)
                trips = repo.get_all(limit=10)
                assert len(trips) == 1, (
                    f"Company {company_id} saw {len(trips)} trips, expected 1"
                )
                assert trips[0]["company_id"] == company_id
                assert trips[0]["client_name"] == expected_name
                return trips[0]

            results = await asyncio.gather(
                _query(10, "C10-Trip"),
                _query(20, "C20-Trip"),
            )
            assert len(results) == 2
        finally:
            _close_db(db)

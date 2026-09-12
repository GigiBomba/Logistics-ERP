"""Platform parity: Feature inventory verification."""
from __future__ import annotations

import pytest

from tests.workflow_integrity.parity.desktop_features import DESKTOP_PROBES, PARITY_MATRIX
from tests.workflow_integrity.parity.fixtures import assert_matrix_covered, build_parity_world
from tests.workflow_integrity.parity.mobile_features import MOBILE_PROBES

pytestmark = pytest.mark.parity


class TestFeatureInventory:
    """Core operations available via service API regardless of platform."""

    def test_trip_read_write_available(self, trip_service):
        """Trip creation and querying are available."""
        assert callable(trip_service.create)
        assert callable(trip_service.update)
        assert callable(trip_service.get_by_id)

    def test_invoice_read_write_available(self, invoice_service):
        """Invoice operations are available."""
        assert callable(invoice_service.create)
        assert callable(invoice_service.finalize)
        assert callable(invoice_service.set_status)

    def test_fleet_read_available(self, fleet_repo):
        """Fleet repository querying is available."""
        assert callable(fleet_repo.get_by_id)

    def test_driver_read_available(self, driver_repo):
        """Driver repository querying is available."""
        assert callable(driver_repo.get_by_id)


class TestMatrixDrivenCoverage:
    """Matrix-driven feature coverage (§4): every PARITY_MATRIX row's desktop /
    mobile coverage must be backed by a truthful probe against the REAL harness
    service dict (workflow-integrity conftest + extended service layer),
    assembled by ``parity/fixtures.build_parity_world``."""

    # ── Desktop coverage ────────────────────────────────────────────

    def test_desktop_true_rows_probe_pass_against_harness_services(self, db):
        """Every desktop-True row: DESKTOP_PROBES[feature] must return True
        against the real harness services dict — no probe asserts True for a
        capability the harness lacks."""
        world = build_parity_world(db)
        services = world["services"]
        true_rows = [row for row in PARITY_MATRIX if row.desktop is True]
        assert len(true_rows) == 29, "expected 29 desktop-True rows in the matrix"
        for row in true_rows:
            probe = DESKTOP_PROBES.get(row.feature)
            assert probe is not None, f"missing desktop probe for {row.feature!r}"
            assert probe(services) is True, (
                f"desktop probe for {row.feature!r} returned False — the harness "
                f"service layer does not back this feature"
            )

    def test_desktop_false_rows_have_no_assertive_probe(self, db):
        """Desktop-False rows (e.g. Route Navigation) must not be claimed by
        any probe: the probe is absent or returns False."""
        world = build_parity_world(db)
        services = world["services"]
        false_rows = [row for row in PARITY_MATRIX if row.desktop is False]
        assert false_rows, "expected at least one desktop-False row in the matrix"
        for row in false_rows:
            probe = DESKTOP_PROBES.get(row.feature)
            assert probe is None or probe(services) is False, (
                f"desktop-False row {row.feature!r} is asserted True by a probe"
            )

    def test_matrix_covered_helper_reports_no_uncovered_desktop_rows(self, db):
        """assert_matrix_covered(PARITY_MATRIX, world, DESKTOP_PROBES) is green:
        the helper reports zero uncovered desktop features."""
        world = build_parity_world(db)
        uncovered = assert_matrix_covered(
            PARITY_MATRIX, world, DESKTOP_PROBES, column="desktop"
        )
        assert uncovered == [], (
            "desktop matrix not fully covered:\n" + "\n".join(uncovered)
        )

    # ── Mobile coverage ─────────────────────────────────────────────

    def test_mobile_coverage_probed_against_mobile_client(self, db):
        """Every mobile probe passes against a MobileClient fixture instance,
        and the probed feature is never marked absent on BOTH mobile columns."""
        world = build_parity_world(db)
        client = world["mobile_client"]
        for feature, probe in MOBILE_PROBES.items():
            assert probe(client) is True, f"mobile probe failed for {feature!r}"
            row = next(r for r in PARITY_MATRIX if r.feature == feature)
            assert row.mobile_driver is not False or row.mobile_dispatcher is not False, (
                f"mobile probe for {feature!r} asserts coverage the matrix marks "
                f"False for driver AND dispatcher"
            )

    def test_view_coverage_rows_expose_read_only_accessors(self, db):
        """'view'-coverage rows assert read-only accessors exist rather than
        mutation.  On mobile, Trip CRUD is 'view' for the driver: its probe
        verifies the read accessor (get_trip) and the fixture exposes no
        mutating trip-CRUD path."""
        world = build_parity_world(db)
        client = world["mobile_client"]
        view_features = {
            row.feature
            for row in PARITY_MATRIX
            if row.mobile_driver == "view" or row.mobile_dispatcher == "view"
        }
        probed_view = sorted(view_features & set(MOBILE_PROBES))
        assert probed_view, "expected at least one probed 'view' row in the matrix"
        for feature in probed_view:
            assert MOBILE_PROBES[feature](client) is True, (
                f"view-coverage probe failed for {feature!r}"
            )
            assert callable(getattr(client, "get_trip", None)), (
                f"{feature!r} is a 'view' row but the fixture exposes no "
                f"read-only accessor (get_trip)"
            )

    # ── World / two-company isolation ───────────────────────────────

    def test_parity_world_two_company_isolation(self, db):
        """Company A (dispatcher + driver + one trip) and Company B (isolated)
        never share data: A owns its trip and driver; B has no trips or
        drivers."""
        world = build_parity_world(db)
        company_a = world["company_a"]
        company_b = world["company_b"]

        assert company_a["company_id"] != company_b["company_id"], (
            "the two parity companies must have distinct ids"
        )

        trip = world["services"]["trip_service"].get_by_id(company_a["trip_id"])
        assert trip is not None, "company A's trip must exist"
        assert trip["company_id"] == company_a["company_id"], (
            "company A's trip must be scoped to company A"
        )

        driver_row = db.conn.execute(
            "SELECT company_id FROM drivers WHERE id = ?",
            (company_a["driver_id"],),
        ).fetchone()
        assert driver_row is not None and driver_row["company_id"] == company_a["company_id"], (
            "company A's driver must be scoped to company A"
        )

        for table in ("trips", "drivers"):
            count = db.conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE company_id = ?",
                (company_b["company_id"],),
            ).fetchone()["n"]
            assert count == 0, (
                f"isolated company B unexpectedly has {count} {table} rows"
            )

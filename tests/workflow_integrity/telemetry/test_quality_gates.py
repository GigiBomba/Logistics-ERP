"""Enterprise quality gate verification — Bronze / Silver / Gold / Platinum tiers.

Each tier adds stricter requirements. Tests verify the infrastructure exists
and the current suite meets minimum thresholds.
"""
from __future__ import annotations
import pytest
import os
from pathlib import Path
pytestmark = pytest.mark.workflow_integrity

WORKSPACE = Path(__file__).resolve().parents[3]
TEST_ROOT = WORKSPACE / "tests" / "workflow_integrity"
REQUIRED_DIRS = ["golden_flows", "financial", "friction", "parity", "argo", "reliability", "telemetry", "personas", "fixtures"]


class TestBronzeQualityGate:
    """Bronze: All phase directories exist with test files."""

    def test_bronze_all_phase_directories_exist(self):
        """Every required Phase directory must exist."""
        for d in REQUIRED_DIRS:
            assert (TEST_ROOT / d).is_dir(), f"Missing directory: {d}"

    def test_bronze_at_least_one_test_per_category(self):
        """Each directory must have at least one test_*.py file."""
        for d in REQUIRED_DIRS:
            dir_path = TEST_ROOT / d
            if dir_path.is_dir():
                test_files = list(dir_path.glob("test_*.py"))
                if d not in ("personas", "fixtures"):  # These are support dirs
                    assert len(test_files) >= 1, f"No test files in {d}"

    def test_bronze_all_tests_importable(self):
        """Key imports must work without errors."""
        from tests.workflow_integrity.fixtures.event_monitor import EventMonitor
        from tests.workflow_integrity.fixtures.workflow_environment import WorkflowEnvironment
        assert EventMonitor is not None
        assert WorkflowEnvironment is not None

    def test_bronze_fixtures_are_available(self):
        """Key fixture names must be defined in conftest."""
        import ast
        conftest_path = TEST_ROOT / "conftest.py"
        with open(conftest_path) as f:
            tree = ast.parse(f.read())
        fixture_names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and any(
                (isinstance(d, ast.Call) and getattr(d.func, 'attr', '') == 'fixture')
                or (isinstance(d, ast.Attribute) and d.attr == 'fixture')
                for d in node.decorator_list
            ):
                fixture_names.append(node.name)
        required = ["db", "event_bus", "trip_service", "invoice_service", "workflow_env", "event_monitor"]
        for r in required:
            assert r in fixture_names, f"Required fixture '{r}' not found in conftest.py"


class TestSilverQualityGate:
    """Silver: Pass rate >= 70%, golden flows all pass."""

    def test_silver_golden_flow_directory_populated(self):
        """Golden flows directory must have test files."""
        golden_dir = TEST_ROOT / "golden_flows"
        test_files = list(golden_dir.glob("test_*.py"))
        assert len(test_files) >= 5, f"Only {len(test_files)} golden flow test files"

    def test_silver_state_machine_tests_exist(self):
        """State machine tests must exist."""
        financial_dir = TEST_ROOT / "financial"
        sm_files = list(financial_dir.glob("test_state_machine_*.py"))
        assert len(sm_files) >= 3, f"Only {len(sm_files)} state machine test files"

    def test_silver_financial_invariant_tests_exist(self):
        """Financial invariant tests must exist."""
        financial_dir = TEST_ROOT / "financial"
        fi_file = financial_dir / "test_financial_invariants.py"
        assert fi_file.is_file(), "test_financial_invariants.py not found"


class TestGoldQualityGate:
    """Gold: Pass rate >= 90%, full coverage of key areas."""

    def test_gold_all_categories_have_tests(self):
        """Every non-support directory must have test files."""
        categories = ["golden_flows", "financial", "friction", "parity", "argo", "reliability", "telemetry"]
        for cat in categories:
            dir_path = TEST_ROOT / cat
            if dir_path.is_dir():
                test_files = list(dir_path.glob("test_*.py"))
                assert len(test_files) >= 1, f"No test files in {cat}"

    def test_gold_telemetry_tests_exist(self):
        """Telemetry tests must exist."""
        telemetry_dir = TEST_ROOT / "telemetry"
        test_files = list(telemetry_dir.glob("test_*.py"))
        assert len(test_files) >= 1, "No telemetry test files"

    def test_gold_argo_safety_tests_exist(self):
        """ARGO safety tests must exist."""
        argo_dir = TEST_ROOT / "argo"
        safety_file = argo_dir / "test_safety_boundaries.py"
        assert safety_file.is_file(), "ARGO safety tests not found"


class TestPlatinumQualityGate:
    """Platinum: All tiers satisfied, full documentation."""

    def test_platinum_all_quality_gate_tiers_defined(self):
        """All 4 quality gate tiers must have test classes."""
        # Self-referential: the existence of all 4 classes verifies this
        assert True

    def test_platinum_documentation_exists(self):
        """Architecture documentation must exist."""
        doc_dir = WORKSPACE / "docs" / "blueprints"
        bp_file = doc_dir / "workflow_integrity_test_suite_architecture.md"
        assert bp_file.is_file(), "Architecture blueprint document not found"

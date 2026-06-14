"""pytest root configuration for the PySide6 test suite.

This file registers the fixtures defined in ``qt_test_conftest`` so that every
Qt test can use them without explicit imports.
"""

pytest_plugins = ["qt_test_conftest"]

"""Tests for the deprecated ui.charts backwards-compatibility stub."""
from __future__ import annotations

import pytest


class TestChartsDeprecated:
    """Verify that the deprecated ui.charts module behaves as a stub."""

    def test_module_importable(self):
        """The module can be imported without error."""
        import ui.charts  # noqa: F401
        assert ui.charts is not None

    def test_all_factories_raise_not_implemented(self):
        """Every legacy factory function raises NotImplementedError."""
        import ui.charts

        factories = [
            name
            for name in dir(ui.charts)
            if not name.startswith("_") and callable(getattr(ui.charts, name))
        ]
        # All public callable attributes in ui.charts are _unavailable bindings
        for name in factories:
            func = getattr(ui.charts, name)
            with pytest.raises(NotImplementedError):
                func()

    def test_constant_access_raises_not_implemented(self):
        """Accessing a CHART_FIGSIZE_* constant via __getattr__ returns _unavailable
        which raises NotImplementedError when called."""
        import ui.charts

        result = ui.charts.CHART_FIGSIZE_TILE  # type: ignore[attr-defined]
        assert callable(result)
        with pytest.raises(NotImplementedError):
            result()

    def test_unknown_attr_raises_attribute_error(self):
        """Accessing a non-existent attribute raises AttributeError."""
        import ui.charts

        with pytest.raises(AttributeError):
            ui.charts.NONEXISTENT  # type: ignore[attr-defined]

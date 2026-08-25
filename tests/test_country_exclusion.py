"""Validation tests for GraphHopper country exclusion pipeline."""
from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

from services.country_exclusion import (
    COUNTRY_BOUNDS,
    CountryExclusionEngine,
    ISO2_TO_ISO3,
)
from services.route_decoder import decode_polyline


def _samples_in_bounds(geometry, iso2: str) -> int:
    bounds = COUNTRY_BOUNDS.get(iso2)
    if not bounds or not geometry:
        return 0
    lon_min, lat_min, lon_max, lat_max = bounds
    step = max(1, len(geometry) // 40)
    count = 0
    for lat, lon in geometry[::step]:
        if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
            count += 1
    return count


class TestCountryExclusionEngine(unittest.TestCase):
    def test_prepare_builds_custom_model(self):
        # data/country_borders.json is gitignored, so CI checkouts don't have
        # it and get_polygons returns [] — the plan would be inactive.  Patch
        # the polygon source with the deterministic FAKE_POLYGONS so this unit
        # test exercises the engine logic without depending on runtime data.
        with patch(
            "services.country_exclusion.get_polygons",
            side_effect=lambda c: FAKE_POLYGONS.get(c, []),
        ):
            engine = CountryExclusionEngine()
            stops = [(44.436, 26.103), (50.110, 8.682)]
            plan = engine.prepare(["HU", "RS"], stops)
            self.assertIn("HU", plan.applied)
            self.assertIn("RS", plan.applied)
            self.assertTrue(plan.active)
            self.assertIn("areas", plan.custom_model)
            self.assertIn("priority", plan.custom_model)
            self.assertEqual(plan.strategy, "custom_model_areas_post")

    def test_skips_exclusion_when_stop_inside_country(self):
        engine = CountryExclusionEngine()
        # Budapest
        stops = [(44.436, 26.103), (47.498, 19.040)]
        plan = engine.prepare(["HU"], stops)
        self.assertIn("HU", plan.skipped_at_stops)
        self.assertNotIn("HU", plan.applied)
        self.assertFalse(plan.active)

    def test_merge_sets_internal_keys(self):
        # Patch get_polygons like test_prepare_builds_custom_model — the real
        # data/country_borders.json is gitignored and absent on CI checkouts.
        with patch(
            "services.country_exclusion.get_polygons",
            side_effect=lambda c: FAKE_POLYGONS.get(c, []),
        ):
            engine = CountryExclusionEngine()
            plan = engine.prepare(["HU"], [(44.436, 26.103), (50.110, 8.682)])
            params = engine.merge_into_params({"weight": "40000"}, plan)
            self.assertIn("_custom_model", params)
            self.assertTrue(params.get("ch.disable"))


@unittest.skipUnless(
    os.environ.get("GRAPHHOPPER_LIVE_TEST") == "1",
    "Set GRAPHHOPPER_LIVE_TEST=1 to run integration tests against GraphHopper",
)
class TestCountryExclusionLive(unittest.TestCase):
    """Compare routes with/without exclusions on a live GraphHopper instance."""

    @classmethod
    def setUpClass(cls):
        import requests

        cls.base = os.environ.get("GRAPHHOPPER_URL", "http://192.168.0.93:8989").rstrip("/")
        cls.session = requests.Session()
        try:
            r = cls.session.get(f"{cls.base}/health", timeout=5)
            if r.status_code >= 500:
                raise unittest.SkipTest("GraphHopper not healthy")
        except Exception as exc:
            raise unittest.SkipTest(f"GraphHopper unavailable: {exc}") from exc

    def _post_route(self, stops, custom_model=None):
        body = {
            "profile": "truck",
            "points": [[lon, lat] for lat, lon in stops],
            "ch.disable": True,
            "points_encoded": True,
        }
        if custom_model:
            body["custom_model"] = custom_model
        r = self.session.post(f"{self.base}/route", json=body, timeout=300)
        self.assertEqual(r.status_code, 200, r.text[:400])
        return r.json()["paths"][0]

    def test_ro_frankfurt_avoid_hungary_changes_geometry(self):
        engine = CountryExclusionEngine()
        stops = [(44.4361414, 26.102684), (50.110, 8.682)]
        plan = engine.prepare(["HU"], stops)
        self.assertTrue(plan.active)

        base = self._post_route(stops)
        avoided = self._post_route(stops, plan.custom_model)

        base_geom = decode_polyline(base["points"])
        avoid_geom = decode_polyline(avoided["points"])

        base_hu = _samples_in_bounds(base_geom, "HU")
        avoid_hu = _samples_in_bounds(avoid_geom, "HU")
        self.assertGreater(base_hu, 0, "baseline should cross Hungary bbox")
        self.assertEqual(avoid_hu, 0, "excluded route should not cross Hungary bbox")
        self.assertGreater(avoided["distance"], base["distance"])

    def test_iso3_catalog_covers_european_ui_list(self):
        from services.country_avoidance import CountryAvoidanceManager

        for code in CountryAvoidanceManager.EUROPEAN_COUNTRIES:
            self.assertIn(code, COUNTRY_BOUNDS)
            self.assertIn(code, ISO2_TO_ISO3)


# ── Additional unit tests ──────────────────────────────────────────

# Patch country_borders so exclusion unit tests don't need real JSON.
FAKE_POLYGONS: dict[str, list[list[list[float]]]] = {
    "HU": [[[46.5, 16.5], [46.5, 22.0], [48.5, 22.0], [48.5, 16.5], [46.5, 16.5]]],
    "RS": [[[42.5, 18.5], [42.5, 23.0], [46.5, 23.0], [46.5, 18.5], [42.5, 18.5]]],
}


class TestExclusionPlan(unittest.TestCase):
    def test_plan_defaults(self):
        from services.country_exclusion import ExclusionPlan

        plan = ExclusionPlan()
        self.assertEqual(plan.requested, [])
        self.assertEqual(plan.applied, [])
        self.assertEqual(plan.strategy, "none")
        self.assertFalse(plan.active)

    def test_plan_active_when_custom_model_set(self):
        from services.country_exclusion import ExclusionPlan

        plan = ExclusionPlan(custom_model={"areas": {}}, applied=["HU"])
        self.assertTrue(plan.active)

    def test_plan_repr(self):
        from services.country_exclusion import ExclusionPlan

        plan = ExclusionPlan(requested=["HU"], applied=["HU"], strategy="test")
        self.assertFalse(plan.active)  # no custom_model


class TestCountryExclusionEngineAdditional(unittest.TestCase):
    def test_skip_empty_excluded_list(self):
        engine = CountryExclusionEngine()
        plan = engine.prepare([], [(44.4, 26.1)])
        self.assertEqual(plan.strategy, "none")
        self.assertFalse(plan.active)

    def test_skip_none_excluded_list(self):
        engine = CountryExclusionEngine()
        plan = engine.prepare(None, [(44.4, 26.1)])
        self.assertEqual(plan.strategy, "none")

    def test_normalize_codes(self):
        normalized = CountryExclusionEngine.normalize_codes(["ro", "DE", "", None, "hU"])
        self.assertEqual(normalized, ["RO", "DE", "HU"])

    def test_normalize_codes_none_input(self):
        self.assertEqual(CountryExclusionEngine.normalize_codes(None), [])

    def test_point_in_bounds_inside(self):
        self.assertTrue(
            CountryExclusionEngine._point_in_bounds(
                17.0, 47.0, (16.5, 46.5, 22.0, 48.5)
            )
        )

    def test_point_in_bounds_outside(self):
        self.assertFalse(
            CountryExclusionEngine._point_in_bounds(
                10.0, 50.0, (16.5, 46.5, 22.0, 48.5)
            )
        )

    @patch("services.country_exclusion.get_polygons", side_effect=lambda c: FAKE_POLYGONS.get(c, []))
    def test_prepare_skips_countries_without_polygon_in_model(self, mock_get):
        engine = CountryExclusionEngine()
        plan = engine.prepare(["XX", "HU"], [(44.4, 26.1)])
        # Both are in applied (applied = requested - stop_countries, regardless of polygons)
        self.assertIn("HU", plan.applied)
        self.assertIn("XX", plan.applied)
        # But the custom_model should only contain areas for countries with polygons
        if plan.custom_model:
            area_keys = list(plan.custom_model.get("areas", {}).keys())
            self.assertIn("avoid_hu", area_keys)
            self.assertNotIn("avoid_xx", area_keys)

    def test_merge_into_params_inactive_plan(self):
        engine = CountryExclusionEngine()
        plan = engine.prepare([], [(44.4, 26.1)])
        params = engine.merge_into_params({"weight": "40000"}, plan)
        self.assertEqual(params, {"weight": "40000"})

    @patch("services.country_exclusion.get_polygons", side_effect=lambda c: FAKE_POLYGONS.get(c, []))
    def test_merge_into_params_adds_keys(self, mock_get):
        engine = CountryExclusionEngine()
        plan = engine.prepare(["HU"], [(44.4, 26.1), (50.1, 8.7)])
        params = engine.merge_into_params({"weight": "40000"}, plan)
        self.assertTrue(params["ch.disable"])
        self.assertEqual(params["avoid_countries"], ["HU"])
        self.assertIn("_custom_model", params)
        self.assertEqual(params["_exclusion_strategy"], "custom_model_areas_post")

    @patch("services.country_exclusion.get_polygons")
    def test_build_custom_model_with_multipolygon(self, mock_get):
        """A country with multiple rings should build a MultiPolygon geometry."""
        mock_get.return_value = [
            [[46.0, 16.0], [46.0, 17.0], [47.0, 17.0], [47.0, 16.0], [46.0, 16.0]],
            [[45.0, 18.0], [45.0, 19.0], [46.0, 19.0], [46.0, 18.0], [45.0, 18.0]],
        ]
        engine = CountryExclusionEngine()
        model = engine._build_custom_model(["XX"])
        self.assertIsNotNone(model)
        self.assertIn("areas", model)
        found_multipolygon = any(
            area["geometry"]["type"] == "MultiPolygon"
            for area in model["areas"].values()
        )
        self.assertTrue(found_multipolygon, "Expected at least one MultiPolygon geometry")


if __name__ == "__main__":
    unittest.main()

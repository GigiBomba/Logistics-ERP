"""Validation tests for GraphHopper country exclusion pipeline."""
import json
import os
import unittest

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


if __name__ == "__main__":
    unittest.main()

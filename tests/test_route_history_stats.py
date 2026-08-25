"""Unit tests for route history statistics labels and totals."""
from __future__ import annotations

import unittest

from services.route_history_service import RouteHistoryService


class TestRouteHistoryStats(unittest.TestCase):
    def test_row_total_cost_prefers_profit_total(self):
        cost = RouteHistoryService._row_total_cost(
            {"total_cost": 150.5},
            {"fuel_cost": 100},
            {"toll_cost": 20},
        )
        self.assertEqual(cost, 150.5)

    def test_row_total_cost_sums_fuel_and_toll(self):
        cost = RouteHistoryService._row_total_cost(
            {},
            {"fuel_cost": 100},
            {"toll_cost": 25},
        )
        self.assertEqual(cost, 125.0)


if __name__ == "__main__":
    unittest.main()

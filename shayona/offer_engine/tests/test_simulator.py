from __future__ import annotations

import unittest

from shayona.offer_engine.simulator import (
    calculate_safe_discount,
    maximum_discount_for_margin,
    simulate_offer,
)


class TestSimulator(unittest.TestCase):
    def setUp(self):
        self.feature = {
            "average_qty_per_order": 100,
            "average_rate": 100,
            "valuation_rate": 70,
            "current_stock": 1000,
            "is_stock_item": True,
            "is_sales_item": True,
            "disabled": False,
            "item_max_discount": 0,
        }
        self.policy = {
            "default_discount_percentage": 5,
            "minimum_discount_percentage": 1,
            "maximum_discount_percentage": 10,
            "minimum_margin_percentage": 15,
            "incremental_quantity_percentage": 20,
        }

    def test_margin_safe_discount_formula(self):
        value = maximum_discount_for_margin(100, 70, 15)
        self.assertAlmostEqual(value, 17.6470588, places=5)

    def test_item_max_discount_can_bind(self):
        discount = calculate_safe_discount({**self.feature, "item_max_discount": 3}, self.policy)
        self.assertEqual(discount, 3)

    def test_margin_cap_can_bind(self):
        discount = calculate_safe_discount(
            {**self.feature, "valuation_rate": 85},
            {
                **self.policy,
                "default_discount_percentage": 10,
                "maximum_discount_percentage": 20,
                "minimum_margin_percentage": 10,
            },
        )
        self.assertAlmostEqual(discount, 5.5556, places=4)

    def test_simulation_buys_incremental_behavior_and_preserves_gp(self):
        result = simulate_offer(self.feature, self.policy)
        self.assertIsNotNone(result)
        self.assertEqual(result["discount_percentage"], 5)
        self.assertEqual(result["minimum_qty"], 126)
        self.assertEqual(result["baseline_gross_profit"], 3000)
        self.assertEqual(result["estimated_gross_profit"], 3150)
        self.assertEqual(result["estimated_incremental_gross_profit"], 150)
        self.assertEqual(result["estimated_discount_cost"], 630)

    def test_rejects_when_safe_discount_is_below_minimum_useful_discount(self):
        result = simulate_offer(
            {**self.feature, "valuation_rate": 85},
            {
                **self.policy,
                "default_discount_percentage": 10,
                "maximum_discount_percentage": 20,
                "minimum_margin_percentage": 10,
                "minimum_discount_percentage": 6,
            },
        )
        self.assertIsNone(result)

    def test_rejects_non_stock_disabled_and_insufficient_stock(self):
        self.assertIsNone(simulate_offer({**self.feature, "is_stock_item": False}, self.policy))
        self.assertIsNone(simulate_offer({**self.feature, "is_sales_item": False}, self.policy))
        self.assertIsNone(simulate_offer({**self.feature, "disabled": True}, self.policy))
        self.assertIsNone(simulate_offer({**self.feature, "past_end_of_life": True}, self.policy))
        self.assertIsNone(simulate_offer({**self.feature, "valuation_rate": 0}, self.policy))
        self.assertIsNone(simulate_offer({**self.feature, "current_stock": 100}, self.policy))


if __name__ == "__main__":
    unittest.main()

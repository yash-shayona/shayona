from __future__ import annotations

import unittest

from shayona.offer_engine.constants import (
    GOAL_CUSTOMER_REACTIVATION,
    GOAL_OVERSTOCK_CLEARANCE,
    GOAL_REACTIVATION_OVERSTOCK,
)
from shayona.offer_engine.detectors import (
    evaluate_candidate,
    is_overstock_candidate,
    is_reactivation_candidate,
    score_candidate,
)


class TestDetectors(unittest.TestCase):
    def setUp(self):
        self.policy = {
            "minimum_customer_item_orders": 2,
            "reactivation_days": 45,
            "overstock_months_threshold": 3,
        }
        self.feature = {
            "purchase_count": 3,
            "net_qty": 50,
            "days_since_last_purchase": 45,
            "is_stock_item": True,
            "current_stock": 300,
            "average_monthly_sales_qty": 100,
            "stock_months": 3,
        }

    def test_reactivation_threshold_is_inclusive(self):
        self.assertTrue(is_reactivation_candidate(self.feature, self.policy))
        self.assertFalse(
            is_reactivation_candidate(
                {**self.feature, "days_since_last_purchase": 44}, self.policy
            )
        )

    def test_reactivation_requires_positive_net_history(self):
        self.assertFalse(is_reactivation_candidate({**self.feature, "net_qty": 0}, self.policy))

    def test_overstock_threshold_is_inclusive(self):
        self.assertTrue(is_overstock_candidate(self.feature, self.policy))
        self.assertFalse(is_overstock_candidate({**self.feature, "stock_months": 2.99}, self.policy))
        self.assertFalse(
            is_overstock_candidate({**self.feature, "average_monthly_sales_qty": 0}, self.policy)
        )

    def test_goal_composition(self):
        self.assertIsNotNone(evaluate_candidate(self.feature, self.policy, GOAL_CUSTOMER_REACTIVATION))
        self.assertIsNotNone(evaluate_candidate(self.feature, self.policy, GOAL_OVERSTOCK_CLEARANCE))
        self.assertIsNotNone(evaluate_candidate(self.feature, self.policy, GOAL_REACTIVATION_OVERSTOCK))
        self.assertIsNone(
            evaluate_candidate(
                {**self.feature, "stock_months": 1}, self.policy, GOAL_REACTIVATION_OVERSTOCK
            )
        )

    def test_score_is_bounded(self):
        score = score_candidate(
            {**self.feature, "days_since_last_purchase": 5000, "stock_months": 5000, "purchase_count": 999},
            self.policy,
            reactivation=True,
            overstock=True,
        )
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


if __name__ == "__main__":
    unittest.main()

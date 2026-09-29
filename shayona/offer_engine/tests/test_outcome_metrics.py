from __future__ import annotations

import unittest

from shayona.offer_engine.outcome_metrics import calculate_outcome


class TestOutcomeMetrics(unittest.TestCase):
    def test_sale_and_return_are_net_evaluated(self):
        rows = [
            {
                "invoice": "SINV-1",
                "is_return": 0,
                "stock_qty": 10,
                "base_net_amount": 900,
                "base_price_list_rate": 100,
                "incoming_rate": 70,
            },
            {
                "invoice": "SINV-RET-1",
                "is_return": 1,
                "stock_qty": -2,
                "base_net_amount": -180,
                "base_price_list_rate": 100,
                "incoming_rate": 70,
            },
        ]
        result = calculate_outcome(rows, baseline_gross_profit_per_order=200)
        self.assertEqual(result["sales_invoice_count"], 1)
        self.assertEqual(result["actual_qty"], 8)
        self.assertEqual(result["actual_revenue"], 720)
        self.assertEqual(result["actual_discount_cost"], 80)
        self.assertEqual(result["actual_gross_profit"], 160)
        self.assertEqual(result["baseline_gross_profit"], 200)
        self.assertEqual(result["estimated_incremental_gross_profit"], -40)
        self.assertTrue(result["converted"])

    def test_no_rows_is_zero_conversion(self):
        result = calculate_outcome([], baseline_gross_profit_per_order=200)
        self.assertEqual(result["sales_invoice_count"], 0)
        self.assertEqual(result["actual_qty"], 0)
        self.assertEqual(result["actual_revenue"], 0)
        self.assertFalse(result["converted"])


if __name__ == "__main__":
    unittest.main()

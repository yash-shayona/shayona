from __future__ import annotations

import unittest
from datetime import date

from shayona.offer_engine.features import build_customer_item_features


class TestFeatures(unittest.TestCase):
    def test_compact_feature_building(self):
        result = build_customer_item_features(
            purchase_rows=[
                {
                    "customer": "CUST-1",
                    "item_code": "ITEM-1",
                    "invoice": "SINV-1",
                    "posting_date": date(2026, 1, 1),
                    "stock_qty": 10,
                    "base_net_amount": 1000,
                },
                {
                    "customer": "CUST-1",
                    "item_code": "ITEM-1",
                    "invoice": "SINV-2",
                    "posting_date": date(2026, 2, 1),
                    "stock_qty": 20,
                    "base_net_amount": 2000,
                },
            ],
            net_rows=[
                {"customer": "CUST-1", "item_code": "ITEM-1", "net_qty": 25, "net_revenue": 2500}
            ],
            company_item_rows=[{"item_code": "ITEM-1", "company_net_qty": 100}],
            stock_rows=[{"item_code": "ITEM-1", "current_stock": 40, "stock_value": 2400}],
            item_metadata=[
                {
                    "name": "ITEM-1",
                    "is_stock_item": 1,
                    "disabled": 0,
                    "stock_uom": "Nos",
                    "max_discount": 7,
                }
            ],
            as_of_date=date(2026, 3, 1),
            lookback_months=10,
        )
        self.assertEqual(len(result), 1)
        row = result[0]
        self.assertEqual(row["purchase_count"], 2)
        self.assertEqual(row["gross_purchase_qty"], 30)
        self.assertEqual(row["net_qty"], 25)
        self.assertEqual(row["average_qty_per_order"], 15)
        self.assertEqual(row["average_rate"], 100)
        self.assertEqual(row["days_since_last_purchase"], 28)
        self.assertEqual(row["average_monthly_sales_qty"], 10)
        self.assertEqual(row["valuation_rate"], 60)
        self.assertEqual(row["stock_months"], 4)
        self.assertEqual(row["stock_uom"], "Nos")
        self.assertEqual(row["item_max_discount"], 7)


if __name__ == "__main__":
    unittest.main()

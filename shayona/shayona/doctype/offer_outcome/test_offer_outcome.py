from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestOfferOutcome(IntegrationTestCase):
    def _outcome(self):
        return frappe.get_doc(
            {
                "doctype": "Offer Outcome",
                "recommendation": "OFREC-TEST",
                "company": "Test Company",
                "customer": "CUST-TEST",
                "item_code": "ITEM-TEST",
                "pricing_rule": "PRLE-TEST",
                "sales_invoice_count": 0,
                "actual_qty": 0,
                "actual_discount_cost": 0,
            }
        )

    def test_negative_qty_fails_before_relationship_lookup(self):
        outcome = self._outcome()
        outcome.actual_qty = -1
        with self.assertRaises(frappe.ValidationError):
            outcome.validate()

    def test_recommendation_field_is_unique(self):
        meta = frappe.get_meta("Offer Outcome")
        self.assertTrue(meta.get_field("recommendation").unique)

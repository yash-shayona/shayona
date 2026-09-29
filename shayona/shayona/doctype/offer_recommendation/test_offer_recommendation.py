from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestOfferRecommendation(IntegrationTestCase):
    def _recommendation(self):
        return frappe.get_doc(
            {
                "doctype": "Offer Recommendation",
                "offer_run": "OFRUN-TEST",
                "offer_policy": "Test Company",
                "company": "Test Company",
                "goal": "Customer Reactivation",
                "customer": "CUST-TEST",
                "score": 50,
                "valid_from": "2026-08-13",
                "valid_upto": "2026-08-22",
                "status": "Proposed",
                "items": [
                    {
                        "doctype": "Offer Recommendation Item",
                        "item_code": "ITEM-TEST",
                        "minimum_qty": 10,
                        "discount_percentage": 5,
                        "offer_rate": 95,
                        "current_stock": 100,
                        "estimated_discount_cost": 50,
                    }
                ],
            }
        )

    def test_invalid_date_range_fails_before_relationship_lookup(self):
        recommendation = self._recommendation()
        recommendation.valid_from = "2026-08-23"
        recommendation.valid_upto = "2026-08-22"
        with self.assertRaises(frappe.ValidationError):
            recommendation.validate()

    def test_invalid_score_fails_before_relationship_lookup(self):
        recommendation = self._recommendation()
        recommendation.score = 101
        with self.assertRaises(frappe.ValidationError):
            recommendation.validate()

    def test_invalid_status_fails_before_relationship_lookup(self):
        recommendation = self._recommendation()
        recommendation.status = "Invalid"
        with self.assertRaises(frappe.ValidationError):
            recommendation.validate()

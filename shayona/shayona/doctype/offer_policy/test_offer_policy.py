from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestOfferPolicy(IntegrationTestCase):
    def _policy(self):
        return frappe.get_doc(
            {
                "doctype": "Offer Policy",
                "company": "Test Company",
                "enabled": 1,
                "default_lookback_months": 12,
                "maximum_lookback_months": 24,
                "reactivation_days": 45,
                "minimum_customer_item_orders": 2,
                "overstock_months_threshold": 3,
                "default_discount_percentage": 5,
                "minimum_discount_percentage": 1,
                "maximum_discount_percentage": 10,
                "minimum_margin_percentage": 15,
                "incremental_quantity_percentage": 20,
                "default_offer_validity_days": 10,
                "max_recommendations_per_run": 20,
            }
        )

    def test_valid_numeric_policy(self):
        self._policy().validate()

    def test_discount_ordering_is_validated(self):
        policy = self._policy()
        policy.maximum_discount_percentage = 4
        with self.assertRaises(frappe.ValidationError):
            policy.validate()


    def test_minimum_useful_discount_must_be_positive(self):
        policy = self._policy()
        policy.minimum_discount_percentage = 0
        with self.assertRaises(frappe.ValidationError):
            policy.validate()

    def test_maximum_lookback_cannot_be_smaller_than_default(self):
        policy = self._policy()
        policy.maximum_lookback_months = 6
        with self.assertRaises(frappe.ValidationError):
            policy.validate()

    def test_margin_must_be_below_100(self):
        policy = self._policy()
        policy.minimum_margin_percentage = 100
        with self.assertRaises(frappe.ValidationError):
            policy.validate()

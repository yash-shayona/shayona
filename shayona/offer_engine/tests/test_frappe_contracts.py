from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase

from shayona.offer_engine.constants import ALGORITHM_VERSION


class IntegrationTestOfferEngineContracts(IntegrationTestCase):
    def test_required_doctypes_and_fields_exist(self):
        expectations = {
            "Offer Policy": ["company", "maximum_lookback_months", "maximum_discount_percentage"],
            "Offer Run": ["company", "goal", "idempotency_key", "analysis_snapshot"],
            "Offer Recommendation": ["offer_run", "customer", "pricing_rule", "items"],
            "Offer Recommendation Item": ["item_code", "minimum_qty", "discount_percentage"],
            "Offer Outcome": ["recommendation", "pricing_rule", "actual_gross_profit"],
        }
        for doctype, fields in expectations.items():
            meta = frappe.get_meta(doctype)
            for field in fields:
                self.assertIsNotNone(meta.get_field(field), f"Missing {doctype}.{field}")

    def test_run_idempotency_key_is_unique(self):
        field = frappe.get_meta("Offer Run").get_field("idempotency_key")
        self.assertTrue(field.unique)

    def test_algorithm_version_is_explicit(self):
        self.assertRegex(ALGORITHM_VERSION, r"^\d+\.\d+\.\d+$")

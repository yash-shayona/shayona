from __future__ import annotations

import frappe
from frappe.tests import IntegrationTestCase


class IntegrationTestOfferRun(IntegrationTestCase):
    def _run(self):
        return frappe.get_doc(
            {
                "doctype": "Offer Run",
                "company": "Test Company",
                "offer_policy": "POLICY-TEST",
                "goal": "Customer Reactivation",
                "lookback_months": 12,
                "source": "API",
                "algorithm_version": "1.0.0",
                "status": "Running",
                "started_at": "2026-08-13 13:20:00",
            }
        )

    def test_valid_contract(self):
        self._run().validate()

    def test_invalid_goal(self):
        run = self._run()
        run.goal = "Random Goal"
        with self.assertRaises(frappe.ValidationError):
            run.validate()

    def test_invalid_source(self):
        run = self._run()
        run.source = "Random Source"
        with self.assertRaises(frappe.ValidationError):
            run.validate()

    def test_non_positive_lookback(self):
        run = self._run()
        run.lookback_months = 0
        with self.assertRaises(frappe.ValidationError):
            run.validate()

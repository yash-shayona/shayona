from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate


class OfferOutcome(Document):
    def validate(self) -> None:
        if self.evaluation_from and self.evaluation_upto and getdate(self.evaluation_from) > getdate(self.evaluation_upto):
            frappe.throw(_("Evaluation From cannot be after Evaluation Upto."))
        if int(self.sales_invoice_count or 0) < 0:
            frappe.throw(_("Attributed Sales Invoice Count cannot be negative."))
        if flt(self.actual_qty) < 0:
            frappe.throw(_("Actual Net Qty cannot be negative."))
        if flt(self.actual_discount_cost) < 0:
            frappe.throw(_("Actual Net Discount Cost cannot be negative."))

        recommendation = frappe.db.get_value(
            "Offer Recommendation",
            self.recommendation,
            ["company", "customer", "pricing_rule"],
            as_dict=True,
        )
        if not recommendation:
            frappe.throw(_("Offer Recommendation {0} does not exist.").format(frappe.bold(self.recommendation)))
        if recommendation.company != self.company or recommendation.customer != self.customer:
            frappe.throw(_("Outcome Company and Customer must match the Offer Recommendation."))
        if recommendation.pricing_rule != self.pricing_rule:
            frappe.throw(_("Outcome Pricing Rule must match the Offer Recommendation Pricing Rule."))

        recommendation_item = frappe.db.get_value(
            "Offer Recommendation Item",
            {"parent": self.recommendation, "parenttype": "Offer Recommendation"},
            "item_code",
        )
        if recommendation_item != self.item_code:
            frappe.throw(_("Outcome Item must match the Offer Recommendation Item."))

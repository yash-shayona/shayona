from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from shayona.offer_engine.constants import GOALS, RECOMMENDATION_STATUSES


class OfferRecommendation(Document):
    def validate(self) -> None:
        self._validate_header()
        self._validate_relationships()
        self._validate_items()

    def _validate_header(self) -> None:
        if self.goal not in GOALS:
            frappe.throw(_("Unsupported Offer Engine goal: {0}").format(frappe.bold(self.goal)))
        if self.status not in RECOMMENDATION_STATUSES:
            frappe.throw(_("Unsupported recommendation status: {0}").format(frappe.bold(self.status)))
        if not (0 <= flt(self.score) <= 100):
            frappe.throw(_("Recommendation Score must be between 0 and 100."))
        if self.valid_from and self.valid_upto and getdate(self.valid_from) > getdate(self.valid_upto):
            frappe.throw(_("Valid From cannot be after Valid Upto."))

    def _validate_relationships(self) -> None:
        run = frappe.db.get_value(
            "Offer Run",
            self.offer_run,
            ["company", "offer_policy", "goal", "customer", "item_code"],
            as_dict=True,
        )
        if not run:
            frappe.throw(_("Offer Run {0} does not exist.").format(frappe.bold(self.offer_run)))
        if run.company != self.company or run.offer_policy != self.offer_policy or run.goal != self.goal:
            frappe.throw(_("Recommendation Company, Policy and Goal must match its Offer Run."))
        if run.customer and run.customer != self.customer:
            frappe.throw(_("Recommendation Customer must match the Customer scoped on the Offer Run."))

        policy_company = frappe.db.get_value("Offer Policy", self.offer_policy, "company")
        if policy_company != self.company:
            frappe.throw(_("Recommendation Company must match its Offer Policy Company."))

        if run.item_code and self.items and self.items[0].item_code != run.item_code:
            frappe.throw(_("Recommendation Item must match the Item scoped on the Offer Run."))

    def _validate_items(self) -> None:
        if len(self.items or []) != 1:
            frappe.throw(_("Offer Engine V1 requires exactly one Item per recommendation."))

        row = self.items[0]
        if flt(row.minimum_qty) <= 0:
            frappe.throw(_("Offer Minimum Qty must be greater than zero."))
        if not (0 <= flt(row.discount_percentage) < 100):
            frappe.throw(_("Discount Percentage must be between 0 and 100 (exclusive of 100)."))
        if flt(row.offer_rate) <= 0:
            frappe.throw(_("Simulated Offer Rate must be greater than zero."))
        if flt(row.current_stock) < 0:
            frappe.throw(_("Current Stock cannot be negative for a generated V1 recommendation."))
        if flt(row.estimated_discount_cost) < 0:
            frappe.throw(_("Estimated Discount Cost cannot be negative."))

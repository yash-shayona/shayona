from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document

from shayona.offer_engine.constants import GOALS, RUN_STATUSES, SOURCES


class OfferRun(Document):
    def validate(self) -> None:
        if not self.offer_policy:
            frappe.throw(_("Offer Policy is required for an Offer Run."))
        if not self.algorithm_version:
            frappe.throw(_("Algorithm Version is required for an Offer Run."))
        if not self.status:
            frappe.throw(_("Status is required for an Offer Run."))
        if not self.started_at:
            frappe.throw(_("Started At is required for an Offer Run."))
        if self.goal not in GOALS:
            frappe.throw(_("Unsupported Offer Engine goal: {0}").format(frappe.bold(self.goal)))
        if self.source not in SOURCES:
            frappe.throw(_("Unsupported Offer Engine source: {0}").format(frappe.bold(self.source)))
        if self.status and self.status not in RUN_STATUSES:
            frappe.throw(_("Unsupported Offer Run status: {0}").format(frappe.bold(self.status)))
        if int(self.lookback_months or 0) <= 0:
            frappe.throw(_("Lookback Months must be greater than zero."))

        if self.offer_policy:
            policy_company = frappe.db.get_value("Offer Policy", self.offer_policy, "company")
            if policy_company and policy_company != self.company:
                frappe.throw(_("Offer Run Company must match the selected Offer Policy Company."))

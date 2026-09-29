from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class OfferPolicy(Document):
    def validate(self) -> None:
        self._validate_detection_settings()
        self._validate_offer_guardrails()
        self._validate_execution_scope()

    def _validate_detection_settings(self) -> None:
        if int(self.default_lookback_months or 0) <= 0:
            frappe.throw(_("Default Lookback Months must be greater than zero."))
        if int(self.maximum_lookback_months or 0) < int(self.default_lookback_months or 0):
            frappe.throw(_("Maximum Lookback Months cannot be smaller than Default Lookback Months."))
        if int(self.reactivation_days or 0) <= 0:
            frappe.throw(_("Reactivation Days must be greater than zero."))
        if int(self.minimum_customer_item_orders or 0) <= 0:
            frappe.throw(_("Minimum Customer-Item Orders must be greater than zero."))
        if flt(self.overstock_months_threshold) <= 0:
            frappe.throw(_("Overstock Months Threshold must be greater than zero."))

    def _validate_offer_guardrails(self) -> None:
        minimum_discount = flt(self.minimum_discount_percentage)
        default_discount = flt(self.default_discount_percentage)
        maximum_discount = flt(self.maximum_discount_percentage)
        minimum_margin = flt(self.minimum_margin_percentage)
        incremental_qty = flt(self.incremental_quantity_percentage)

        if not (0 < minimum_discount <= default_discount <= maximum_discount < 100):
            frappe.throw(
                _(
                    "Discount guardrails must satisfy 0 < Minimum Useful Discount <= "
                    "Default Discount <= Maximum Discount < 100."
                )
            )
        if not (0 <= minimum_margin < 100):
            frappe.throw(_("Minimum Margin must be between 0 and 100 (exclusive of 100)."))
        if incremental_qty <= 0:
            frappe.throw(_("Incremental Quantity Target must be greater than zero."))
        if int(self.default_offer_validity_days or 0) <= 0:
            frappe.throw(_("Default Offer Validity Days must be greater than zero."))
        if int(self.max_recommendations_per_run or 0) <= 0:
            frappe.throw(_("Max Recommendations per Run must be greater than zero."))

    def _validate_execution_scope(self) -> None:
        if self.warehouse:
            warehouse = frappe.db.get_value(
                "Warehouse",
                self.warehouse,
                ["company", "is_group"],
                as_dict=True,
            )
            if not warehouse:
                frappe.throw(_("Warehouse {0} does not exist.").format(frappe.bold(self.warehouse)))
            if warehouse.company != self.company:
                frappe.throw(_("The selected Warehouse must belong to the Offer Policy Company."))
            if warehouse.is_group:
                frappe.throw(_("A group Warehouse cannot be used as the Offer Engine execution scope."))

        if self.price_list:
            price_list = frappe.db.get_value(
                "Price List",
                self.price_list,
                ["selling", "enabled"],
                as_dict=True,
            )
            if not price_list:
                frappe.throw(_("Price List {0} does not exist.").format(frappe.bold(self.price_list)))
            if not price_list.selling:
                frappe.throw(_("The selected Price List must be enabled for Selling."))
            if not price_list.enabled:
                frappe.throw(_("The selected Price List must be enabled."))

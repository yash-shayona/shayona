from __future__ import annotations

import frappe
from frappe import _

ALLOWED_ROLES = {"System Manager", "Sales Manager"}


def require_offer_engine_role() -> None:
    roles = set(frappe.get_roles())
    if not roles.intersection(ALLOWED_ROLES):
        frappe.throw(
            _("You need the System Manager or Sales Manager role to use the Offer Engine."),
            frappe.PermissionError,
        )


def check_company_read(company: str) -> None:
    require_offer_engine_role()
    company_doc = frappe.get_doc("Company", company)
    company_doc.check_permission("read")


def check_optional_scope(customer: str | None = None, item_code: str | None = None) -> None:
    if customer:
        frappe.get_doc("Customer", customer).check_permission("read")
    if item_code:
        frappe.get_doc("Item", item_code).check_permission("read")


def check_analysis_access(company: str, customer: str | None = None, item_code: str | None = None) -> None:
    check_company_read(company)
    check_optional_scope(customer=customer, item_code=item_code)


def check_recommendation_write(recommendation) -> None:
    require_offer_engine_role()
    recommendation.check_permission("write")
    check_company_read(recommendation.company)
    item_code = recommendation.items[0].item_code if len(recommendation.items or []) == 1 else None
    check_optional_scope(customer=recommendation.customer, item_code=item_code)


def check_pricing_rule_create_permission() -> None:
    if not frappe.has_permission("Pricing Rule", "create"):
        frappe.throw(
            _("You do not have permission to create a Pricing Rule."),
            frappe.PermissionError,
        )

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from . import data_access
from .constants import (
    FLOAT_TOLERANCE,
    RECOMMENDATION_STATUS_ACTIVATED,
    RECOMMENDATION_STATUS_EVALUATED,
    RECOMMENDATION_STATUS_PROPOSED,
    RECOMMENDATION_STATUS_REJECTED,
)
from .permissions import (
    check_pricing_rule_create_permission,
    check_recommendation_write,
)
from .simulator import simulate_offer


def _policy_values(policy) -> dict:
    return {
        "default_discount_percentage": policy.default_discount_percentage,
        "minimum_discount_percentage": policy.minimum_discount_percentage,
        "maximum_discount_percentage": policy.maximum_discount_percentage,
        "minimum_margin_percentage": policy.minimum_margin_percentage,
        "incremental_quantity_percentage": policy.incremental_quantity_percentage,
    }


def _validate_recommendation_for_activation(recommendation, policy) -> None:
    if recommendation.status in (RECOMMENDATION_STATUS_ACTIVATED, RECOMMENDATION_STATUS_EVALUATED):
        return
    if recommendation.status != RECOMMENDATION_STATUS_PROPOSED:
        frappe.throw(
            _("Only a Proposed recommendation can be approved and activated. Current status: {0}").format(
                frappe.bold(recommendation.status)
            )
        )
    if not policy.enabled:
        frappe.throw(_("The Offer Policy is disabled. Run analysis again after enabling a valid policy."))
    if len(recommendation.items or []) != 1:
        frappe.throw(_("Offer Engine V1 requires exactly one Item per recommendation."))
    if getdate(recommendation.valid_upto) < getdate(today()):
        frappe.throw(_("This recommendation has expired. Run a new analysis before approval."))


def _current_financial_position(recommendation, policy) -> tuple[dict, dict]:
    row = recommendation.items[0]
    item_metadata = data_access.get_item_metadata([row.item_code])
    if not item_metadata:
        frappe.throw(_("Item {0} no longer exists.").format(frappe.bold(row.item_code)))
    item = item_metadata[0]
    stock_rows = data_access.get_stock_rows(
        company=recommendation.company,
        item_codes=[row.item_code],
        warehouse=policy.warehouse,
    )
    stock = stock_rows[0] if stock_rows else {}
    current_stock = flt(stock.get("current_stock"))
    stock_value = flt(stock.get("stock_value"))
    valuation_rate = stock_value / current_stock if current_stock > 0 and stock_value >= 0 else 0.0

    feature = {
        "average_qty_per_order": flt(row.historical_avg_qty),
        "average_rate": flt(row.historical_avg_rate),
        "valuation_rate": valuation_rate,
        "current_stock": current_stock,
        "is_stock_item": bool(item.get("is_stock_item")),
        "is_sales_item": bool(item.get("is_sales_item")),
        "disabled": bool(item.get("disabled")),
        "past_end_of_life": bool(
            item.get("end_of_life") and getdate(item.get("end_of_life")) < getdate(today())
        ),
        "item_max_discount": flt(item.get("max_discount")),
    }
    return feature, item


def _revalidate_financial_guardrails(recommendation, policy) -> None:
    row = recommendation.items[0]
    feature, _item = _current_financial_position(recommendation, policy)
    simulation = simulate_offer(feature, _policy_values(policy))
    if not simulation:
        frappe.throw(
            _("The recommendation is no longer financially safe with current stock/cost or policy guardrails. Run analysis again.")
        )
    if flt(row.discount_percentage) > flt(simulation["discount_percentage"]) + FLOAT_TOLERANCE:
        frappe.throw(
            _("The stored discount is no longer allowed by current margin/discount guardrails. Run analysis again.")
        )
    if flt(row.minimum_qty) + FLOAT_TOLERANCE < flt(simulation["minimum_qty"]):
        frappe.throw(
            _("The stored minimum quantity no longer preserves the current break-even guardrail. Run analysis again.")
        )


def find_conflicting_pricing_rule(*, recommendation, policy) -> str | None:
    row = recommendation.items[0]
    pricing_rule = frappe.qb.DocType("Pricing Rule")
    pricing_rule_item = frappe.qb.DocType("Pricing Rule Item Code")

    query = (
        frappe.qb.from_(pricing_rule)
        .inner_join(pricing_rule_item)
        .on(pricing_rule_item.parent == pricing_rule.name)
        .select(pricing_rule.name)
        .where(pricing_rule.docstatus < 2)
        .where(pricing_rule.disable == 0)
        .where(pricing_rule.selling == 1)
        .where(pricing_rule.apply_on == "Item Code")
        .where(pricing_rule.applicable_for == "Customer")
        .where(pricing_rule.customer == recommendation.customer)
        .where(pricing_rule_item.item_code == row.item_code)
        .where(
            pricing_rule.company.isnull()
            | (pricing_rule.company == "")
            | (pricing_rule.company == recommendation.company)
        )
        .where(
            pricing_rule.valid_from.isnull()
            | (pricing_rule.valid_from <= recommendation.valid_upto)
        )
        .where(
            pricing_rule.valid_upto.isnull()
            | (pricing_rule.valid_upto >= recommendation.valid_from)
        )
    )

    if policy.price_list:
        query = query.where(
            pricing_rule.for_price_list.isnull()
            | (pricing_rule.for_price_list == "")
            | (pricing_rule.for_price_list == policy.price_list)
        )
    if policy.warehouse:
        query = query.where(
            pricing_rule.warehouse.isnull()
            | (pricing_rule.warehouse == "")
            | (pricing_rule.warehouse == policy.warehouse)
        )

    rows = query.limit(1).run(as_dict=True)
    return rows[0].get("name") if rows else None


def _pricing_rule_currency(recommendation, policy) -> str:
    if policy.price_list:
        currency = frappe.db.get_value("Price List", policy.price_list, "currency")
        if currency:
            return currency
    return frappe.get_cached_value("Company", recommendation.company, "default_currency")


def _create_pricing_rule(recommendation, policy):
    row = recommendation.items[0]
    conflict = find_conflicting_pricing_rule(recommendation=recommendation, policy=policy)
    if conflict:
        frappe.throw(
            _("Conflicting active Pricing Rule {0} already covers this Customer, Item and validity scope.").format(
                frappe.bold(conflict)
            )
        )

    pricing_rule = frappe.new_doc("Pricing Rule")
    pricing_rule.title = f"Offer Engine {recommendation.name}"
    pricing_rule.apply_on = "Item Code"
    pricing_rule.price_or_product_discount = "Price"
    pricing_rule.selling = 1
    pricing_rule.buying = 0
    pricing_rule.applicable_for = "Customer"
    pricing_rule.customer = recommendation.customer
    pricing_rule.company = recommendation.company
    pricing_rule.currency = _pricing_rule_currency(recommendation, policy)
    pricing_rule.min_qty = flt(row.minimum_qty)
    pricing_rule.valid_from = recommendation.valid_from
    pricing_rule.valid_upto = recommendation.valid_upto
    pricing_rule.rate_or_discount = "Discount Percentage"
    pricing_rule.discount_percentage = flt(row.discount_percentage)
    pricing_rule.for_price_list = policy.price_list
    pricing_rule.warehouse = policy.warehouse
    pricing_rule.rule_description = _("Generated from Offer Recommendation {0}.").format(
        recommendation.name
    )
    pricing_rule.append(
        "items",
        {
            "item_code": row.item_code,
            "uom": row.stock_uom,
        },
    )
    pricing_rule.insert()
    return pricing_rule


def approve_recommendation(name: str) -> dict:
    recommendation = frappe.get_doc("Offer Recommendation", name)
    check_recommendation_write(recommendation)

    if recommendation.status in (RECOMMENDATION_STATUS_ACTIVATED, RECOMMENDATION_STATUS_EVALUATED):
        if recommendation.pricing_rule and frappe.db.exists("Pricing Rule", recommendation.pricing_rule):
            return {
                "recommendation": recommendation.name,
                "status": recommendation.status,
                "pricing_rule": recommendation.pricing_rule,
                "idempotent": True,
            }
        frappe.throw(_("Recommendation is marked activated but its generated Pricing Rule is missing."))

    policy = frappe.get_doc("Offer Policy", recommendation.offer_policy)
    policy.check_permission("read")
    _validate_recommendation_for_activation(recommendation, policy)
    check_pricing_rule_create_permission()
    _revalidate_financial_guardrails(recommendation, policy)

    pricing_rule = _create_pricing_rule(recommendation, policy)
    now = now_datetime()
    recommendation.approved_by = frappe.session.user
    recommendation.approved_on = now
    recommendation.activated_on = now
    recommendation.pricing_rule = pricing_rule.name
    recommendation.status = RECOMMENDATION_STATUS_ACTIVATED
    recommendation.save()

    return {
        "recommendation": recommendation.name,
        "status": recommendation.status,
        "pricing_rule": pricing_rule.name,
        "idempotent": False,
    }


def reject_recommendation(name: str, reason: str | None = None) -> dict:
    recommendation = frappe.get_doc("Offer Recommendation", name)
    check_recommendation_write(recommendation)

    if recommendation.status == RECOMMENDATION_STATUS_REJECTED:
        return {
            "recommendation": recommendation.name,
            "status": recommendation.status,
            "idempotent": True,
        }
    if recommendation.status != RECOMMENDATION_STATUS_PROPOSED:
        frappe.throw(
            _("Only a Proposed recommendation can be rejected. Current status: {0}").format(
                frappe.bold(recommendation.status)
            )
        )

    recommendation.status = RECOMMENDATION_STATUS_REJECTED
    recommendation.rejected_by = frappe.session.user
    recommendation.rejected_on = now_datetime()
    recommendation.rejection_reason = (reason or "").strip() or None
    recommendation.save()
    return {
        "recommendation": recommendation.name,
        "status": recommendation.status,
        "idempotent": False,
    }

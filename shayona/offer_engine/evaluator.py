from __future__ import annotations

from datetime import date

import frappe
from frappe import _
from frappe.utils import flt, getdate, now_datetime, today

from .constants import RECOMMENDATION_STATUS_EVALUATED
from .data_access import get_attributed_sales_rows
from .outcome_metrics import calculate_outcome
from .permissions import check_recommendation_write


def _evaluation_upto(valid_upto, evaluation_date: date) -> date:
    valid_upto = getdate(valid_upto)
    return min(valid_upto, evaluation_date)


def evaluate_recommendation(name: str) -> dict:
    recommendation = frappe.get_doc("Offer Recommendation", name)
    check_recommendation_write(recommendation)
    if not recommendation.pricing_rule:
        frappe.throw(_("The recommendation must be activated before it can be evaluated."))
    if len(recommendation.items or []) != 1:
        frappe.throw(_("Offer Engine V1 requires exactly one Item per recommendation."))

    row = recommendation.items[0]
    evaluation_date = getdate(today())
    evaluation_upto = _evaluation_upto(recommendation.valid_upto, evaluation_date)
    rows = get_attributed_sales_rows(
        pricing_rule=recommendation.pricing_rule,
        company=recommendation.company,
        customer=recommendation.customer,
        item_code=row.item_code,
        valid_from=getdate(recommendation.valid_from),
        valid_upto=evaluation_upto,
        evaluation_date=evaluation_date,
    )
    metrics = calculate_outcome(
        rows,
        baseline_gross_profit_per_order=flt(row.baseline_gross_profit),
    )

    outcome_name = frappe.db.exists("Offer Outcome", {"recommendation": recommendation.name})
    if outcome_name:
        outcome = frappe.get_doc("Offer Outcome", outcome_name)
        outcome.check_permission("write")
    else:
        outcome = frappe.new_doc("Offer Outcome")
        outcome.recommendation = recommendation.name
        outcome.company = recommendation.company
        outcome.customer = recommendation.customer
        outcome.item_code = row.item_code
        outcome.pricing_rule = recommendation.pricing_rule

    outcome.evaluation_from = recommendation.valid_from
    outcome.evaluation_upto = evaluation_upto
    outcome.evaluated_on = now_datetime()
    for field, value in metrics.items():
        outcome.set(field, value)

    if outcome.is_new():
        outcome.insert()
    else:
        outcome.save()

    recommendation.status = RECOMMENDATION_STATUS_EVALUATED
    recommendation.evaluated_on = outcome.evaluated_on
    recommendation.save()

    return {
        "name": outcome.name,
        "recommendation": recommendation.name,
        "company": outcome.company,
        "customer": outcome.customer,
        "item_code": outcome.item_code,
        "pricing_rule": outcome.pricing_rule,
        "evaluation_from": outcome.evaluation_from,
        "evaluation_upto": outcome.evaluation_upto,
        "evaluated_on": outcome.evaluated_on,
        **metrics,
    }

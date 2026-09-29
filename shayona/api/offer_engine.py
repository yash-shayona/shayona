from __future__ import annotations

import frappe

from shayona.offer_engine.engine import (
    get_recommendation_result,
    get_run_result,
    run_analysis as run_analysis_service,
)
from shayona.offer_engine.evaluator import evaluate_recommendation as evaluate_recommendation_service
from shayona.offer_engine.pricing import (
    approve_recommendation as approve_recommendation_service,
    reject_recommendation as reject_recommendation_service,
)


@frappe.whitelist(methods=["POST"])
def run_analysis(
    company: str,
    goal: str,
    customer: str | None = None,
    item_code: str | None = None,
    lookback_months: int | str | None = None,
    source: str = "API",
    external_request_id: str | None = None,
):
    return run_analysis_service(
        company=company,
        goal=goal,
        customer=customer,
        item_code=item_code,
        lookback_months=lookback_months,
        source=source,
        external_request_id=external_request_id,
    )


@frappe.whitelist(methods=["GET"])
def get_run(name: str):
    return get_run_result(name)


@frappe.whitelist(methods=["GET"])
def get_recommendation(name: str):
    return get_recommendation_result(name)


@frappe.whitelist(methods=["POST"])
def approve_recommendation(name: str):
    return approve_recommendation_service(name)


@frappe.whitelist(methods=["POST"])
def reject_recommendation(name: str, reason: str | None = None):
    return reject_recommendation_service(name, reason=reason)


@frappe.whitelist(methods=["POST"])
def evaluate_recommendation(name: str):
    return evaluate_recommendation_service(name)

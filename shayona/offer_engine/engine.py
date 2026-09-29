from __future__ import annotations

import hashlib
import json
from datetime import date

import frappe
from frappe import _
from frappe.utils import add_days, add_months, getdate, now_datetime, today

from . import data_access
from .constants import (
    ALGORITHM_VERSION,
    GOALS,
    RUN_STATUS_COMPLETED,
    RUN_STATUS_FAILED,
    RUN_STATUS_RUNNING,
    SOURCES,
)
from .detectors import evaluate_candidate
from .features import build_customer_item_features
from .permissions import check_analysis_access
from .simulator import simulate_offer


def _idempotency_key(company: str, source: str, external_request_id: str | None) -> str | None:
    external_request_id = (external_request_id or "").strip()
    if not external_request_id:
        return None
    raw = f"{company}\x1f{source}\x1f{external_request_id}".encode()
    return hashlib.sha256(raw).hexdigest()


def _load_policy(company: str):
    if not frappe.db.exists("Offer Policy", company):
        frappe.throw(
            _("Create an enabled Offer Policy for Company {0} before running analysis.").format(
                frappe.bold(company)
            )
        )
    policy = frappe.get_doc("Offer Policy", company)
    policy.check_permission("read")
    if not policy.enabled:
        frappe.throw(_("Offer Policy for Company {0} is disabled.").format(frappe.bold(company)))
    return policy


def _normalize_lookback(policy, lookback_months: int | str | None) -> int:
    value = int(lookback_months or policy.default_lookback_months or 0)
    if value <= 0:
        frappe.throw(_("Lookback Months must be greater than zero."))
    if value > int(policy.maximum_lookback_months or 0):
        frappe.throw(
            _("Lookback Months cannot exceed the Offer Policy maximum of {0}.").format(
                policy.maximum_lookback_months
            )
        )
    return value


def _policy_dict(policy) -> dict:
    fields = (
        "minimum_customer_item_orders",
        "reactivation_days",
        "overstock_months_threshold",
        "default_discount_percentage",
        "minimum_discount_percentage",
        "maximum_discount_percentage",
        "minimum_margin_percentage",
        "incremental_quantity_percentage",
    )
    return {field: policy.get(field) for field in fields}


def _reason_text(feature: dict, reason_codes: list[str]) -> str:
    parts: list[str] = []
    if "REACTIVATION" in reason_codes:
        parts.append(
            _("Customer has not purchased this item for {0} days after {1} historical purchase event(s).").format(
                feature.get("days_since_last_purchase"), feature.get("purchase_count")
            )
        )
    if "OVERSTOCK" in reason_codes:
        parts.append(
            _("Current stock represents approximately {0} months of company-wide historical movement.").format(
                feature.get("stock_months")
            )
        )
    return " ".join(parts)


def _recommendation_item(feature: dict, simulation: dict) -> dict:
    return {
        "item_code": feature.get("item_code"),
        "stock_uom": feature.get("stock_uom"),
        "purchase_count": feature.get("purchase_count"),
        "last_purchase_date": feature.get("last_purchase_date"),
        "days_since_last_purchase": feature.get("days_since_last_purchase"),
        "historical_net_qty": feature.get("net_qty"),
        "historical_avg_qty": feature.get("average_qty_per_order"),
        "historical_avg_rate": feature.get("average_rate"),
        "company_avg_monthly_sales_qty": feature.get("average_monthly_sales_qty"),
        "current_stock": feature.get("current_stock"),
        "stock_months": feature.get("stock_months"),
        "valuation_rate": feature.get("valuation_rate"),
        "item_max_discount": feature.get("item_max_discount"),
        "baseline_qty": simulation.get("baseline_qty"),
        "baseline_revenue": simulation.get("baseline_revenue"),
        "baseline_gross_profit": simulation.get("baseline_gross_profit"),
        "minimum_qty": simulation.get("minimum_qty"),
        "discount_percentage": simulation.get("discount_percentage"),
        "offer_rate": simulation.get("offer_rate"),
        "offer_margin_percentage": simulation.get("offer_margin_percentage"),
        "expected_qty": simulation.get("expected_qty"),
        "estimated_revenue": simulation.get("estimated_revenue"),
        "estimated_discount_cost": simulation.get("estimated_discount_cost"),
        "estimated_gross_profit": simulation.get("estimated_gross_profit"),
        "estimated_incremental_gross_profit": simulation.get("estimated_incremental_gross_profit"),
        "estimated_stock_reduction": simulation.get("estimated_stock_reduction"),
    }


def _build_snapshot(
    *,
    company: str,
    goal: str,
    customer: str | None,
    item_code: str | None,
    from_date: date,
    to_date: date,
    feature_count: int,
    eligible_count: int,
    selected: list[dict],
) -> dict:
    return {
        "schema_version": 1,
        "company": company,
        "goal": goal,
        "scope": {"customer": customer, "item_code": item_code},
        "period": {"from": str(from_date), "to": str(to_date)},
        "feature_count": feature_count,
        "eligible_candidate_count": eligible_count,
        "selected_recommendation_count": len(selected),
        "selected_candidates": [
            {
                "customer": candidate["feature"].get("customer"),
                "item_code": candidate["feature"].get("item_code"),
                "score": candidate["detection"].get("score"),
                "reason_codes": candidate["detection"].get("reason_codes"),
                "days_since_last_purchase": candidate["feature"].get("days_since_last_purchase"),
                "stock_months": candidate["feature"].get("stock_months"),
                "minimum_qty": candidate["simulation"].get("minimum_qty"),
                "discount_percentage": candidate["simulation"].get("discount_percentage"),
                "estimated_incremental_gross_profit": candidate["simulation"].get(
                    "estimated_incremental_gross_profit"
                ),
            }
            for candidate in selected
        ],
    }


def _create_recommendation(*, run, policy, candidate: dict, company_currency: str):
    feature = candidate["feature"]
    detection = candidate["detection"]
    simulation = candidate["simulation"]
    valid_from = getdate(today())
    validity_days = int(policy.default_offer_validity_days or 1)
    valid_upto = add_days(valid_from, validity_days - 1)

    recommendation = frappe.new_doc("Offer Recommendation")
    recommendation.offer_run = run.name
    recommendation.offer_policy = policy.name
    recommendation.company = run.company
    recommendation.goal = run.goal
    recommendation.customer = feature.get("customer")
    recommendation.score = detection.get("score")
    recommendation.reason_codes = ",".join(detection.get("reason_codes") or [])
    recommendation.reason = _reason_text(feature, detection.get("reason_codes") or [])
    recommendation.currency = company_currency
    recommendation.valid_from = valid_from
    recommendation.valid_upto = valid_upto
    recommendation.status = "Proposed"
    recommendation.append("items", _recommendation_item(feature, simulation))
    recommendation.insert()
    return recommendation


def run_analysis(
    *,
    company: str,
    goal: str,
    customer: str | None = None,
    item_code: str | None = None,
    lookback_months: int | str | None = None,
    source: str = "API",
    external_request_id: str | None = None,
) -> dict:
    company = (company or "").strip()
    goal = (goal or "").strip()
    customer = (customer or "").strip() or None
    item_code = (item_code or "").strip() or None
    source = (source or "API").strip()
    external_request_id = (external_request_id or "").strip() or None

    if not company:
        frappe.throw(_("Company is required."))
    if goal not in GOALS:
        frappe.throw(_("Unsupported Offer Engine goal: {0}").format(frappe.bold(goal)))
    if source not in SOURCES:
        frappe.throw(_("Unsupported Offer Engine source: {0}").format(frappe.bold(source)))

    check_analysis_access(company, customer=customer, item_code=item_code)
    policy = _load_policy(company)
    lookback = _normalize_lookback(policy, lookback_months)
    request_key = _idempotency_key(company, source, external_request_id)

    if request_key:
        existing = frappe.db.exists("Offer Run", {"idempotency_key": request_key})
        if existing:
            return get_run_result(existing)

    as_of_date = getdate(today())
    from_date = add_months(as_of_date, -lookback)

    run = frappe.new_doc("Offer Run")
    run.company = company
    run.offer_policy = policy.name
    run.goal = goal
    run.customer = customer
    run.item_code = item_code
    run.lookback_months = lookback
    run.source = source
    run.external_request_id = external_request_id
    run.idempotency_key = request_key
    run.algorithm_version = ALGORITHM_VERSION
    run.status = RUN_STATUS_RUNNING
    run.started_at = now_datetime()
    run.recommendation_count = 0
    if request_key:
        insert_savepoint = "offer_engine_idempotency_insert"
        frappe.db.savepoint(insert_savepoint)
        try:
            run.insert()
        except frappe.DuplicateEntryError:
            frappe.db.rollback(save_point=insert_savepoint)
            existing = frappe.db.exists("Offer Run", {"idempotency_key": request_key})
            if existing:
                return get_run_result(existing)
            raise
    else:
        run.insert()

    savepoint = f"offer_engine_{run.name.replace('-', '_')}"
    frappe.db.savepoint(savepoint)

    try:
        purchase_rows = data_access.get_purchase_rows(
            company=company,
            from_date=from_date,
            to_date=as_of_date,
            customer=customer,
            item_code=item_code,
            warehouse=policy.warehouse,
        )
        item_codes = sorted({row.get("item_code") for row in purchase_rows if row.get("item_code")})

        net_rows = data_access.get_net_customer_item_rows(
            company=company,
            from_date=from_date,
            to_date=as_of_date,
            customer=customer,
            item_code=item_code,
            warehouse=policy.warehouse,
        )
        company_item_rows = data_access.get_company_item_rows(
            company=company,
            from_date=from_date,
            to_date=as_of_date,
            item_code=item_code,
            warehouse=policy.warehouse,
        )
        stock_rows = data_access.get_stock_rows(
            company=company,
            item_codes=item_codes,
            warehouse=policy.warehouse,
        )
        item_metadata = data_access.get_item_metadata(item_codes)

        features = build_customer_item_features(
            purchase_rows=purchase_rows,
            net_rows=net_rows,
            company_item_rows=company_item_rows,
            stock_rows=stock_rows,
            item_metadata=item_metadata,
            as_of_date=as_of_date,
            lookback_months=lookback,
        )

        policy_values = _policy_dict(policy)
        candidates: list[dict] = []
        for feature in features:
            detection = evaluate_candidate(feature, policy_values, goal)
            if not detection:
                continue
            simulation = simulate_offer(feature, policy_values)
            if not simulation:
                continue
            candidates.append(
                {"feature": feature, "detection": detection, "simulation": simulation}
            )

        candidates.sort(
            key=lambda candidate: (
                float(candidate["detection"].get("score") or 0),
                float(candidate["simulation"].get("estimated_incremental_gross_profit") or 0),
                float(candidate["feature"].get("purchase_count") or 0),
            ),
            reverse=True,
        )
        selected = candidates[: int(policy.max_recommendations_per_run or 0)]
        company_currency = frappe.get_cached_value("Company", company, "default_currency")

        recommendation_names: list[str] = []
        for candidate in selected:
            recommendation = _create_recommendation(
                run=run,
                policy=policy,
                candidate=candidate,
                company_currency=company_currency,
            )
            recommendation_names.append(recommendation.name)

        snapshot = _build_snapshot(
            company=company,
            goal=goal,
            customer=customer,
            item_code=item_code,
            from_date=from_date,
            to_date=as_of_date,
            feature_count=len(features),
            eligible_count=len(candidates),
            selected=selected,
        )
        run.analysis_snapshot = json.dumps(snapshot, sort_keys=True, default=str)
        run.recommendation_count = len(recommendation_names)
        run.status = RUN_STATUS_COMPLETED
        run.completed_at = now_datetime()
        run.error_message = None
        run.save()
        return get_run_result(run.name)
    except Exception:
        frappe.db.rollback(save_point=savepoint)
        run = frappe.get_doc("Offer Run", run.name)
        run.status = RUN_STATUS_FAILED
        run.completed_at = now_datetime()
        run.recommendation_count = 0
        run.error_message = _("Analysis failed. See Error Log for technical details.")
        run.save()
        frappe.log_error(message=frappe.get_traceback(), title=f"Offer Engine analysis failed: {run.name}")
        return get_run_result(run.name)


def _parse_snapshot(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError):
        return {}


def get_run_result(name: str) -> dict:
    run = frappe.get_doc("Offer Run", name)
    run.check_permission("read")
    check_analysis_access(run.company, customer=run.customer, item_code=run.item_code)
    recommendations = frappe.get_list(
        "Offer Recommendation",
        filters={"offer_run": run.name},
        fields=["name", "customer", "status", "score", "pricing_rule"],
        order_by="score desc, name asc",
    )
    return {
        "name": run.name,
        "company": run.company,
        "goal": run.goal,
        "customer": run.customer,
        "item_code": run.item_code,
        "lookback_months": run.lookback_months,
        "source": run.source,
        "external_request_id": run.external_request_id,
        "algorithm_version": run.algorithm_version,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "recommendation_count": run.recommendation_count,
        "analysis_snapshot": _parse_snapshot(run.analysis_snapshot),
        "error_message": run.error_message,
        "recommendations": recommendations,
    }


def get_recommendation_result(name: str) -> dict:
    recommendation = frappe.get_doc("Offer Recommendation", name)
    recommendation.check_permission("read")
    item_code = recommendation.items[0].item_code if len(recommendation.items or []) == 1 else None
    check_analysis_access(
        recommendation.company,
        customer=recommendation.customer,
        item_code=item_code,
    )
    outcome = frappe.db.exists("Offer Outcome", {"recommendation": recommendation.name})
    return {
        "name": recommendation.name,
        "offer_run": recommendation.offer_run,
        "offer_policy": recommendation.offer_policy,
        "company": recommendation.company,
        "goal": recommendation.goal,
        "customer": recommendation.customer,
        "score": recommendation.score,
        "reason_codes": [code for code in (recommendation.reason_codes or "").split(",") if code],
        "reason": recommendation.reason,
        "currency": recommendation.currency,
        "valid_from": recommendation.valid_from,
        "valid_upto": recommendation.valid_upto,
        "status": recommendation.status,
        "approved_by": recommendation.approved_by,
        "approved_on": recommendation.approved_on,
        "activated_on": recommendation.activated_on,
        "pricing_rule": recommendation.pricing_rule,
        "rejected_by": recommendation.rejected_by,
        "rejected_on": recommendation.rejected_on,
        "rejection_reason": recommendation.rejection_reason,
        "evaluated_on": recommendation.evaluated_on,
        "items": [row.as_dict() for row in recommendation.items],
        "outcome": outcome,
    }

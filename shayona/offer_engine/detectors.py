from __future__ import annotations

from .constants import (
    GOAL_CUSTOMER_REACTIVATION,
    GOAL_OVERSTOCK_CLEARANCE,
    GOAL_REACTIVATION_OVERSTOCK,
    REASON_OVERSTOCK,
    REASON_REACTIVATION,
)


def is_reactivation_candidate(feature: dict, policy: dict) -> bool:
    return bool(
        feature.get("purchase_count", 0) >= policy.get("minimum_customer_item_orders", 0)
        and feature.get("net_qty", 0) > 0
        and feature.get("days_since_last_purchase", -1) >= policy.get("reactivation_days", 0)
    )


def is_overstock_candidate(feature: dict, policy: dict) -> bool:
    return bool(
        feature.get("is_stock_item")
        and feature.get("current_stock", 0) > 0
        and feature.get("average_monthly_sales_qty", 0) > 0
        and feature.get("stock_months", 0) >= policy.get("overstock_months_threshold", 0)
    )


def score_candidate(feature: dict, policy: dict, *, reactivation: bool, overstock: bool) -> float:
    score = 0.0

    if reactivation:
        threshold = max(float(policy.get("reactivation_days", 1) or 1), 1.0)
        inactivity_ratio = float(feature.get("days_since_last_purchase", 0)) / threshold
        score += 45.0 + min(20.0, max(0.0, inactivity_ratio - 1.0) * 10.0)

    if overstock:
        threshold = max(float(policy.get("overstock_months_threshold", 1) or 1), 0.01)
        stock_ratio = float(feature.get("stock_months", 0)) / threshold
        score += 25.0 + min(10.0, max(0.0, stock_ratio - 1.0) * 5.0)

    purchase_count = max(float(feature.get("purchase_count", 0)), 0.0)
    score += min(10.0, purchase_count)

    return round(min(100.0, max(0.0, score)), 2)


def evaluate_candidate(feature: dict, policy: dict, goal: str) -> dict | None:
    reactivation = is_reactivation_candidate(feature, policy)
    overstock = is_overstock_candidate(feature, policy)

    if goal == GOAL_CUSTOMER_REACTIVATION and not reactivation:
        return None
    if goal == GOAL_OVERSTOCK_CLEARANCE and not overstock:
        return None
    if goal == GOAL_REACTIVATION_OVERSTOCK and not (reactivation and overstock):
        return None

    reason_codes: list[str] = []
    if reactivation:
        reason_codes.append(REASON_REACTIVATION)
    if overstock:
        reason_codes.append(REASON_OVERSTOCK)

    return {
        "reason_codes": reason_codes,
        "score": score_candidate(
            feature,
            policy,
            reactivation=reactivation,
            overstock=overstock,
        ),
    }

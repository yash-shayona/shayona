from __future__ import annotations

import math

from .constants import BREAK_EVEN_SAFETY_FACTOR, FLOAT_TOLERANCE


def _number(value) -> float:
    return float(value or 0)


def maximum_discount_for_margin(base_price: float, cost_rate: float, minimum_margin_percentage: float) -> float:
    base_price = _number(base_price)
    cost_rate = _number(cost_rate)
    minimum_margin_percentage = _number(minimum_margin_percentage)

    if base_price <= 0 or cost_rate < 0 or minimum_margin_percentage < 0 or minimum_margin_percentage >= 100:
        return 0.0

    minimum_offer_rate = cost_rate / (1.0 - (minimum_margin_percentage / 100.0))
    if minimum_offer_rate >= base_price:
        return 0.0

    return max(0.0, min(100.0, (1.0 - (minimum_offer_rate / base_price)) * 100.0))


def calculate_safe_discount(feature: dict, policy: dict) -> float:
    base_price = _number(feature.get("average_rate"))
    cost_rate = _number(feature.get("valuation_rate"))

    caps = [
        _number(policy.get("default_discount_percentage")),
        _number(policy.get("maximum_discount_percentage")),
        maximum_discount_for_margin(
            base_price,
            cost_rate,
            _number(policy.get("minimum_margin_percentage")),
        ),
    ]

    item_max_discount = _number(feature.get("item_max_discount"))
    if item_max_discount > 0:
        caps.append(item_max_discount)

    return round(max(0.0, min(caps)), 4) if caps else 0.0


def simulate_offer(feature: dict, policy: dict) -> dict | None:
    if (
        not feature.get("is_stock_item")
        or not feature.get("is_sales_item", True)
        or feature.get("disabled")
        or feature.get("past_end_of_life")
    ):
        return None

    baseline_qty = _number(feature.get("average_qty_per_order"))
    base_price = _number(feature.get("average_rate"))
    cost_rate = _number(feature.get("valuation_rate"))
    current_stock = _number(feature.get("current_stock"))

    if baseline_qty <= 0 or base_price <= 0 or cost_rate <= 0 or current_stock <= 0:
        return None

    discount_percentage = calculate_safe_discount(feature, policy)
    if discount_percentage + FLOAT_TOLERANCE < _number(policy.get("minimum_discount_percentage")):
        return None

    offer_rate = base_price * (1.0 - discount_percentage / 100.0)
    offer_unit_profit = offer_rate - cost_rate
    baseline_unit_profit = base_price - cost_rate

    if offer_rate <= 0 or offer_unit_profit <= 0 or baseline_unit_profit < 0:
        return None

    minimum_margin_percentage = _number(policy.get("minimum_margin_percentage"))
    offer_margin_percentage = (offer_unit_profit / offer_rate) * 100.0
    if offer_margin_percentage + FLOAT_TOLERANCE < minimum_margin_percentage:
        return None

    incremental_factor = 1.0 + (_number(policy.get("incremental_quantity_percentage")) / 100.0)
    target_qty = baseline_qty * incremental_factor

    baseline_gross_profit = baseline_qty * baseline_unit_profit
    break_even_qty = baseline_gross_profit / offer_unit_profit if offer_unit_profit > 0 else math.inf
    minimum_qty = max(target_qty, break_even_qty * BREAK_EVEN_SAFETY_FACTOR)
    minimum_qty = round(minimum_qty, 4)

    if minimum_qty <= 0 or current_stock + FLOAT_TOLERANCE < minimum_qty:
        return None

    expected_qty = minimum_qty
    baseline_revenue = baseline_qty * base_price
    offer_revenue = expected_qty * offer_rate
    discount_cost = expected_qty * max(0.0, base_price - offer_rate)
    offer_gross_profit = expected_qty * offer_unit_profit
    incremental_gross_profit = offer_gross_profit - baseline_gross_profit

    if incremental_gross_profit < -FLOAT_TOLERANCE:
        return None

    return {
        "baseline_qty": round(baseline_qty, 4),
        "baseline_rate": round(base_price, 4),
        "valuation_rate": round(cost_rate, 4),
        "baseline_revenue": round(baseline_revenue, 2),
        "baseline_gross_profit": round(baseline_gross_profit, 2),
        "minimum_qty": minimum_qty,
        "discount_percentage": round(discount_percentage, 4),
        "offer_rate": round(offer_rate, 4),
        "offer_margin_percentage": round(offer_margin_percentage, 4),
        "expected_qty": round(expected_qty, 4),
        "estimated_revenue": round(offer_revenue, 2),
        "estimated_discount_cost": round(discount_cost, 2),
        "estimated_gross_profit": round(offer_gross_profit, 2),
        "estimated_incremental_gross_profit": round(max(0.0, incremental_gross_profit), 2),
        "estimated_stock_reduction": round(min(current_stock, expected_qty), 4),
    }

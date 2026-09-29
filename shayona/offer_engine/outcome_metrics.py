from __future__ import annotations


def _number(value) -> float:
    return float(value or 0)


def _line_metrics(row: dict) -> tuple[float, float, float, float]:
    qty = _number(row.get("stock_qty"))
    revenue = _number(row.get("base_net_amount"))
    list_rate = _number(row.get("base_price_list_rate"))
    incoming_rate = _number(row.get("incoming_rate"))
    list_revenue = qty * list_rate
    discount_cost = list_revenue - revenue
    gross_profit = revenue - (qty * incoming_rate)
    return qty, revenue, discount_cost, gross_profit


def calculate_outcome(rows: list[dict], *, baseline_gross_profit_per_order: float) -> dict:
    sales_invoice_names = {
        row.get("invoice")
        for row in rows
        if row.get("invoice") and not int(row.get("is_return") or 0)
    }
    actual_qty = 0.0
    actual_revenue = 0.0
    actual_discount_cost = 0.0
    actual_gross_profit = 0.0

    for row in rows:
        qty, revenue, discount_cost, gross_profit = _line_metrics(row)
        actual_qty += qty
        actual_revenue += revenue
        actual_discount_cost += discount_cost
        actual_gross_profit += gross_profit

    invoice_count = len(sales_invoice_names)
    baseline_gross_profit = _number(baseline_gross_profit_per_order) * invoice_count
    simple_incremental_gp = actual_gross_profit - baseline_gross_profit

    return {
        "sales_invoice_count": invoice_count,
        "actual_qty": round(max(0.0, actual_qty), 4),
        "actual_revenue": round(actual_revenue, 2),
        "actual_discount_cost": round(max(0.0, actual_discount_cost), 2),
        "actual_gross_profit": round(actual_gross_profit, 2),
        "baseline_gross_profit": round(baseline_gross_profit, 2),
        "estimated_incremental_gross_profit": round(simple_incremental_gp, 2),
        "converted": bool(actual_qty > 0 and actual_revenue > 0),
    }

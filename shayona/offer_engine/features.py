from __future__ import annotations

from collections import defaultdict
from datetime import date


def _number(value) -> float:
    return float(value or 0)


def _date(value) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def aggregate_purchase_rows(rows: list[dict]) -> dict[tuple[str, str], dict]:
    aggregated: dict[tuple[str, str], dict] = defaultdict(
        lambda: {
            "purchase_count": 0,
            "gross_purchase_qty": 0.0,
            "gross_purchase_revenue": 0.0,
            "last_purchase_date": None,
        }
    )

    for row in rows:
        customer = row.get("customer")
        item_code = row.get("item_code")
        if not customer or not item_code:
            continue

        key = (customer, item_code)
        data = aggregated[key]
        data["purchase_count"] += 1
        data["gross_purchase_qty"] += _number(row.get("stock_qty"))
        data["gross_purchase_revenue"] += _number(row.get("base_net_amount"))
        posting_date = _date(row.get("posting_date"))
        if posting_date and (not data["last_purchase_date"] or posting_date > data["last_purchase_date"]):
            data["last_purchase_date"] = posting_date

    return dict(aggregated)


def build_customer_item_features(
    *,
    purchase_rows: list[dict],
    net_rows: list[dict],
    company_item_rows: list[dict],
    stock_rows: list[dict],
    item_metadata: list[dict],
    as_of_date: date,
    lookback_months: int,
) -> list[dict]:
    purchases = aggregate_purchase_rows(purchase_rows)
    net_map = {
        (row.get("customer"), row.get("item_code")): {
            "net_qty": _number(row.get("net_qty")),
            "net_revenue": _number(row.get("net_revenue")),
        }
        for row in net_rows
        if row.get("customer") and row.get("item_code")
    }
    company_item_map = {
        row.get("item_code"): _number(row.get("company_net_qty"))
        for row in company_item_rows
        if row.get("item_code")
    }
    stock_map = {
        row.get("item_code"): {
            "current_stock": _number(row.get("current_stock")),
            "stock_value": _number(row.get("stock_value")),
        }
        for row in stock_rows
        if row.get("item_code")
    }
    metadata_map = {row.get("name"): row for row in item_metadata if row.get("name")}

    features: list[dict] = []
    months = max(int(lookback_months or 1), 1)

    for key, purchase in purchases.items():
        customer, item_code = key
        metadata = metadata_map.get(item_code, {})
        net = net_map.get(key, {})
        stock = stock_map.get(item_code, {})

        purchase_count = int(purchase.get("purchase_count") or 0)
        gross_qty = _number(purchase.get("gross_purchase_qty"))
        gross_revenue = _number(purchase.get("gross_purchase_revenue"))
        net_qty = _number(net.get("net_qty"))
        net_revenue = _number(net.get("net_revenue"))
        average_qty = gross_qty / purchase_count if purchase_count > 0 else 0.0
        average_rate = gross_revenue / gross_qty if gross_qty > 0 else 0.0
        company_net_qty = _number(company_item_map.get(item_code))
        average_monthly_sales_qty = company_net_qty / months if company_net_qty > 0 else 0.0
        current_stock = _number(stock.get("current_stock"))
        stock_value = _number(stock.get("stock_value"))
        valuation_rate = stock_value / current_stock if current_stock > 0 and stock_value >= 0 else 0.0
        stock_months = current_stock / average_monthly_sales_qty if average_monthly_sales_qty > 0 else 0.0
        last_purchase_date = purchase.get("last_purchase_date")
        days_since_last_purchase = (
            (as_of_date - last_purchase_date).days if last_purchase_date else -1
        )

        features.append(
            {
                "customer": customer,
                "item_code": item_code,
                "purchase_count": purchase_count,
                "gross_purchase_qty": round(gross_qty, 4),
                "gross_purchase_revenue": round(gross_revenue, 2),
                "net_qty": round(net_qty, 4),
                "net_revenue": round(net_revenue, 2),
                "average_qty_per_order": round(average_qty, 4),
                "average_rate": round(average_rate, 4),
                "last_purchase_date": last_purchase_date,
                "days_since_last_purchase": days_since_last_purchase,
                "company_net_qty": round(company_net_qty, 4),
                "average_monthly_sales_qty": round(average_monthly_sales_qty, 4),
                "current_stock": round(current_stock, 4),
                "stock_value": round(stock_value, 2),
                "valuation_rate": round(valuation_rate, 4),
                "stock_months": round(stock_months, 4),
                "is_stock_item": bool(metadata.get("is_stock_item")),
                "is_sales_item": bool(metadata.get("is_sales_item")),
                "disabled": bool(metadata.get("disabled")),
                "end_of_life": _date(metadata.get("end_of_life")),
                "past_end_of_life": bool(
                    metadata.get("end_of_life")
                    and _date(metadata.get("end_of_life")) < as_of_date
                ),
                "stock_uom": metadata.get("stock_uom"),
                "item_max_discount": _number(metadata.get("max_discount")),
            }
        )

    return features

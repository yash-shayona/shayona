from __future__ import annotations

from datetime import date

import frappe
from frappe.query_builder.functions import Sum


def _base_sales_query(
    *, company: str, from_date: date, to_date: date, customer=None, item_code=None, warehouse=None
):
    sales_invoice = frappe.qb.DocType("Sales Invoice")
    sales_invoice_item = frappe.qb.DocType("Sales Invoice Item")
    query = (
        frappe.qb.from_(sales_invoice)
        .inner_join(sales_invoice_item)
        .on(sales_invoice_item.parent == sales_invoice.name)
        .where(sales_invoice.docstatus == 1)
        .where(sales_invoice.company == company)
        .where(sales_invoice.posting_date >= from_date)
        .where(sales_invoice.posting_date <= to_date)
        .where(sales_invoice_item.item_code != "")
    )
    if customer:
        query = query.where(sales_invoice.customer == customer)
    if item_code:
        query = query.where(sales_invoice_item.item_code == item_code)
    if warehouse:
        query = query.where(sales_invoice_item.warehouse == warehouse)
    return query, sales_invoice, sales_invoice_item


def get_purchase_rows(
    *, company: str, from_date: date, to_date: date, customer=None, item_code=None, warehouse=None
) -> list[dict]:
    query, sales_invoice, item = _base_sales_query(
        company=company,
        from_date=from_date,
        to_date=to_date,
        customer=customer,
        item_code=item_code,
        warehouse=warehouse,
    )
    return (
        query.where(sales_invoice.is_return == 0)
        .select(
            sales_invoice.customer,
            item.item_code,
            sales_invoice.name.as_("invoice"),
            sales_invoice.posting_date,
            Sum(item.stock_qty).as_("stock_qty"),
            Sum(item.base_net_amount).as_("base_net_amount"),
        )
        .groupby(
            sales_invoice.customer,
            item.item_code,
            sales_invoice.name,
            sales_invoice.posting_date,
        )
        .run(as_dict=True)
    )


def get_net_customer_item_rows(
    *, company: str, from_date: date, to_date: date, customer=None, item_code=None, warehouse=None
) -> list[dict]:
    query, sales_invoice, item = _base_sales_query(
        company=company,
        from_date=from_date,
        to_date=to_date,
        customer=customer,
        item_code=item_code,
        warehouse=warehouse,
    )
    return (
        query.select(
            sales_invoice.customer,
            item.item_code,
            Sum(item.stock_qty).as_("net_qty"),
            Sum(item.base_net_amount).as_("net_revenue"),
        )
        .groupby(sales_invoice.customer, item.item_code)
        .run(as_dict=True)
    )


def get_company_item_rows(
    *, company: str, from_date: date, to_date: date, item_code=None, warehouse=None
) -> list[dict]:
    query, _sales_invoice, item = _base_sales_query(
        company=company,
        from_date=from_date,
        to_date=to_date,
        item_code=item_code,
        warehouse=warehouse,
    )
    return (
        query.select(
            item.item_code,
            Sum(item.stock_qty).as_("company_net_qty"),
        )
        .groupby(item.item_code)
        .run(as_dict=True)
    )


def get_stock_rows(*, company: str, item_codes: list[str], warehouse: str | None = None) -> list[dict]:
    if not item_codes:
        return []

    bin_table = frappe.qb.DocType("Bin")
    warehouse_table = frappe.qb.DocType("Warehouse")
    query = (
        frappe.qb.from_(bin_table)
        .inner_join(warehouse_table)
        .on(warehouse_table.name == bin_table.warehouse)
        .select(
            bin_table.item_code,
            Sum(bin_table.actual_qty).as_("current_stock"),
            Sum(bin_table.stock_value).as_("stock_value"),
        )
        .where(warehouse_table.company == company)
        .where(warehouse_table.is_group == 0)
        .where(bin_table.item_code.isin(item_codes))
        .groupby(bin_table.item_code)
    )
    if warehouse:
        query = query.where(bin_table.warehouse == warehouse)
    return query.run(as_dict=True)


def get_item_metadata(item_codes: list[str]) -> list[dict]:
    if not item_codes:
        return []
    return frappe.get_list(
        "Item",
        filters={"name": ["in", item_codes]},
        fields=["name", "is_stock_item", "is_sales_item", "disabled", "end_of_life", "stock_uom", "max_discount"],
    )


def get_attributed_sales_rows(
    *,
    pricing_rule: str,
    company: str,
    customer: str,
    item_code: str,
    valid_from: date,
    valid_upto: date,
    evaluation_date: date,
) -> list[dict]:
    sales_invoice = frappe.qb.DocType("Sales Invoice")
    item = frappe.qb.DocType("Sales Invoice Item")
    pricing_detail = frappe.qb.DocType("Pricing Rule Detail")

    sales_rows = (
        frappe.qb.from_(pricing_detail)
        .inner_join(sales_invoice)
        .on(sales_invoice.name == pricing_detail.parent)
        .inner_join(item)
        .on(item.name == pricing_detail.child_docname)
        .select(
            sales_invoice.name.as_("invoice"),
            sales_invoice.posting_date,
            sales_invoice.is_return,
            item.stock_qty,
            item.base_net_amount,
            item.base_price_list_rate,
            item.incoming_rate,
        )
        .where(pricing_detail.parenttype == "Sales Invoice")
        .where(pricing_detail.pricing_rule == pricing_rule)
        .where(pricing_detail.rule_applied == 1)
        .where(sales_invoice.docstatus == 1)
        .where(sales_invoice.is_return == 0)
        .where(sales_invoice.company == company)
        .where(sales_invoice.customer == customer)
        .where(item.item_code == item_code)
        .where(sales_invoice.posting_date >= valid_from)
        .where(sales_invoice.posting_date <= valid_upto)
        .run(as_dict=True)
    )

    invoice_names = sorted({row.get("invoice") for row in sales_rows if row.get("invoice")})
    if not invoice_names:
        return []

    return_rows = (
        frappe.qb.from_(sales_invoice)
        .inner_join(item)
        .on(item.parent == sales_invoice.name)
        .select(
            sales_invoice.name.as_("invoice"),
            sales_invoice.posting_date,
            sales_invoice.is_return,
            item.stock_qty,
            item.base_net_amount,
            item.base_price_list_rate,
            item.incoming_rate,
        )
        .where(sales_invoice.docstatus == 1)
        .where(sales_invoice.is_return == 1)
        .where(sales_invoice.company == company)
        .where(sales_invoice.customer == customer)
        .where(sales_invoice.return_against.isin(invoice_names))
        .where(item.item_code == item_code)
        .where(sales_invoice.posting_date <= evaluation_date)
        .run(as_dict=True)
    )

    return [*sales_rows, *return_rows]

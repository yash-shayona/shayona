import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate

import erpnext


def _require_sales_order_create_permission():
    if not frappe.has_permission("Sales Order", "create"):
        frappe.throw(
            _("You do not have permission to create a Sales Order."),
            frappe.PermissionError,
        )


def _get_items(items):
    if isinstance(items, str):
        items = frappe.parse_json(items)

    if not isinstance(items, list) or not items:
        frappe.throw(_("Please add at least one item."))

    return items


def _build_sales_order(customer, transaction_date, items):
    customer = cstr(customer).strip()
    if not customer:
        frappe.throw(_("Please select a Customer."))

    if not transaction_date:
        frappe.throw(_("Please select an Order Date."))

    transaction_date = getdate(transaction_date)

    sales_order = frappe.new_doc("Sales Order")
    sales_order.company = sales_order.company or erpnext.get_default_company()
    if not sales_order.company:
        frappe.throw(_("Please set a default Company for your user."))

    sales_order.customer = customer
    sales_order.transaction_date = transaction_date
    sales_order.delivery_date = transaction_date
    sales_order.order_type = sales_order.order_type or "Sales"
    sales_order.set("items", [])

    for index, raw_item in enumerate(_get_items(items), start=1):
        if not isinstance(raw_item, dict):
            frappe.throw(_("Row {0}: Invalid item data.").format(index))

        item = frappe._dict(raw_item)
        item_code = cstr(item.item_code).strip()
        qty = flt(item.qty)

        if not item_code:
            frappe.throw(_("Row {0}: Item Code is required.").format(index))

        if qty <= 0:
            frappe.throw(
                _("Row {0}: Quantity must be greater than zero.").format(index)
            )

        item_values = {
            "item_code": item_code,
            "qty": qty,
            "delivery_date": transaction_date,
        }

        # Rate is absent during preview pricing and present when saving the displayed row.
        if "rate" in item:
            rate = flt(item.rate)
            if rate < 0:
                frappe.throw(_("Row {0}: Rate cannot be negative.").format(index))
            item_values["rate"] = rate

        sales_order.append("items", item_values)

    # Apply document-level user permissions to the selected company, customer, and items.
    sales_order.check_permission("create")

    # Reuse ERPNext's party, price list, item, warehouse, tax, and total calculation flow.
    sales_order.run_method("set_missing_values")
    sales_order.calculate_taxes_and_totals()
    return sales_order


@frappe.whitelist()
def get_item_defaults(customer, transaction_date, item_code, qty=1):
    _require_sales_order_create_permission()
    sales_order = _build_sales_order(
        customer,
        transaction_date,
        [{"item_code": item_code, "qty": qty}],
    )
    item = sales_order.items[0]

    return {
        "item_code": item.item_code,
        "item_name": item.item_name,
        "uom": item.uom,
        "rate": item.rate,
        "currency": sales_order.currency,
    }


@frappe.whitelist(methods=["POST"])
def create_sales_order(customer, transaction_date, items):
    _require_sales_order_create_permission()
    sales_order = _build_sales_order(customer, transaction_date, items)
    sales_order.insert()

    return {"name": sales_order.name, "doctype": sales_order.doctype}

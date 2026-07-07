from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from helpdesk.consts import DEFAULT_TICKET_TEMPLATE
from helpdesk.utils import get_customer

CONFIG_DOCTYPE = "Helpdesk Customer Config"
ADMIN_CHILD_DOCTYPE = "Helpdesk Customer Admin User"
ADMIN_CHILD_PARENTFIELD = "admin_users"


def get_user_customers(user: str | None = None) -> list[str]:
    user = user or frappe.session.user
    return list(get_customer(user) or [])


def _get_child_config_names_for_admin(user: str) -> list[str]:
    return frappe.get_all(
        ADMIN_CHILD_DOCTYPE,
        filters={
            "user": user,
            "parenttype": CONFIG_DOCTYPE,
            "parentfield": ADMIN_CHILD_PARENTFIELD,
        },
        pluck="parent",
    )


def get_admin_customers(user: str | None = None) -> list[str]:
    user = user or frappe.session.user
    customers = set(
        frappe.get_all(
            CONFIG_DOCTYPE,
            filters={"active": 1, "admin_user": user},  # backward compatibility
            pluck="customer",
        )
        or []
    )

    config_names = _get_child_config_names_for_admin(user)
    if config_names:
        customers.update(
            frappe.get_all(
                CONFIG_DOCTYPE,
                filters={"active": 1, "name": ["in", config_names]},
                pluck="customer",
            )
            or []
        )

    return sorted(c for c in customers if c)


def get_customer_config(customer: str | None) -> dict[str, Any] | None:
    if not customer:
        return None

    config_name = frappe.db.get_value(
        CONFIG_DOCTYPE,
        {"customer": customer, "active": 1},
        "name",
    )
    if not config_name:
        return None

    doc = frappe.get_cached_doc(CONFIG_DOCTYPE, config_name)

    allowed_templates = [row.template for row in (doc.allowed_templates or []) if row.template]
    admin_users = [row.user for row in (doc.admin_users or []) if row.user]
    if not admin_users and doc.admin_user:
        admin_users = [doc.admin_user]

    return {
        "name": doc.name,
        "customer": doc.customer,
        "admin_users": admin_users,
        "allowed_templates": allowed_templates,
    }


def get_customer_allowed_templates(customer: str | None) -> list[str]:
    config = get_customer_config(customer)
    if not config:
        return [DEFAULT_TICKET_TEMPLATE]

    allowed_templates = config["allowed_templates"] or []
    return allowed_templates or [DEFAULT_TICKET_TEMPLATE]


def get_customer_template_options(customer: str | None) -> list[dict[str, str]]:
    return [
        {"label": template, "value": template}
        for template in get_customer_allowed_templates(customer)
    ]


def get_customer_primary_template(customer: str | None) -> str:
    allowed_templates = get_customer_allowed_templates(customer)
    return allowed_templates[0] if allowed_templates else DEFAULT_TICKET_TEMPLATE


def resolve_effective_template(
    requested_template: str | None = None,
    customer: str | None = None,
    user: str | None = None,
) -> str:
    requested_template = (requested_template or "").strip()
    user = user or frappe.session.user

    if not customer:
        customers = get_user_customers(user)
        customer = customers[0] if customers else None

    config = get_customer_config(customer)
    explicit_request = bool(
        requested_template and requested_template != DEFAULT_TICKET_TEMPLATE
    )

    if not config:
        return requested_template or DEFAULT_TICKET_TEMPLATE

    allowed_templates = config["allowed_templates"] or []
    primary_template = (
        allowed_templates[0] if allowed_templates else DEFAULT_TICKET_TEMPLATE
    )

    if explicit_request:
        if requested_template in allowed_templates:
            return requested_template

        frappe.throw(
            _("Template '{0}' is not allowed for customer '{1}'.").format(
                requested_template, config["customer"]
            ),
            frappe.PermissionError,
        )

    return primary_template


def resolve_ticket_customer_from_doc(
    doc: dict[str, Any], user: str | None = None
) -> str | None:
    user = user or frappe.session.user

    if doc.get("customer"):
        return doc["customer"]

    customers = get_user_customers(user)
    return customers[0] if customers else None
from __future__ import annotations

import frappe
from helpdesk.helpdesk.doctype.hd_ticket import hd_ticket as core_hd_ticket

from shayona.services.helpdesk_customer_template_service import get_admin_customers

INTERNAL_HELPDESK_ROLES = {"System Manager", "Agent Manager", "Agent"}


def _get_roles(user: str) -> set[str]:
    return set(frappe.get_roles(user))


def _is_internal_helpdesk_user(user: str) -> bool:
    if user == "Administrator":
        return True

    if _get_roles(user) & INTERNAL_HELPDESK_ROLES:
        return True

    return bool(frappe.db.exists("HD Agent", {"user": user}))


def _get_contact_names_for_user(user: str) -> list[str]:
    contact_names = set(
        frappe.get_all("Contact", filters={"email_id": user}, pluck="name") or []
    )
    linked_contact_names = set(
        frappe.get_all("Contact", filters={"user": user}, pluck="name") or []
    )
    return list(contact_names | linked_contact_names)


def get_permission_query_conditions(user=None):
    user = user or frappe.session.user

    if user == "Administrator":
        return None

    if _is_internal_helpdesk_user(user):
        return core_hd_ticket.permission_query(user)

    escaped_user = frappe.db.escape(user, percent=False)
    conditions = [
        f"`tabHD Ticket`.`owner` = {escaped_user}",
        f"`tabHD Ticket`.`raised_by` = {escaped_user}",
    ]

    contact_names = _get_contact_names_for_user(user)
    if contact_names:
        contacts_sql = ", ".join(
            frappe.db.escape(name, percent=False) for name in contact_names
        )
        conditions.append(f"`tabHD Ticket`.`contact` in ({contacts_sql})")

    admin_customers = get_admin_customers(user)
    if admin_customers:
        customers_sql = ", ".join(
            frappe.db.escape(customer, percent=False) for customer in admin_customers
        )
        conditions.append(f"`tabHD Ticket`.`customer` in ({customers_sql})")

    return "(" + " OR ".join(conditions) + ")"


def has_permission(doc, user=None, ptype=None, debug=False):
    user = user or frappe.session.user

    if user == "Administrator":
        return True

    if _is_internal_helpdesk_user(user):
        return core_hd_ticket.has_permission(doc, user)

    if doc.owner == user or doc.raised_by == user:
        return True

    if doc.contact in set(_get_contact_names_for_user(user)):
        return True

    if doc.customer in set(get_admin_customers(user)):
        return True

    return False
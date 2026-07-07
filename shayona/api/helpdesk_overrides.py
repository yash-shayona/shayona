from __future__ import annotations
from typing import Any
import frappe
from helpdesk.helpdesk.doctype.hd_ticket import api as hd_ticket_api
from helpdesk.helpdesk.doctype.hd_ticket_template import api as hd_ticket_template_api

from shayona.services.helpdesk_customer_template_service import (
    get_customer_template_options,
    resolve_effective_template,
    resolve_ticket_customer_from_doc,
)


def _resolve_customer(doc: dict[str, Any] | None = None) -> str | None:
    return resolve_ticket_customer_from_doc(doc or {})


@frappe.whitelist()
def get_one(name: str):
    customer = _resolve_customer()
    effective_template = resolve_effective_template(
        requested_template=name,
        customer=customer,
    )

    data = hd_ticket_template_api.get_one(effective_template) or {
        "about": None,
        "fields": [],
        "description_template": "",
    }

    data["_selected_template"] = effective_template
    data["_allowed_templates"] = get_customer_template_options(customer)

    return data


@frappe.whitelist()
def new_ticket(doc: dict[str, Any], attachments: list[dict] | None = None):
    parsed_doc = frappe.parse_json(doc) if isinstance(doc, str) else (doc or {})
    attachments = attachments or []

    customer = _resolve_customer(parsed_doc)
    parsed_doc["template"] = resolve_effective_template(
        requested_template=parsed_doc.get("template"),
        customer=customer,
    )

    if customer and not parsed_doc.get("customer"):
        parsed_doc["customer"] = customer

    if parsed_doc.get("subject"):
        parsed_doc["subject"] = str(parsed_doc["subject"]).strip()

    if parsed_doc.get("description"):
        parsed_doc["description"] = str(parsed_doc["description"]).strip()

    return hd_ticket_api.new(doc=parsed_doc, attachments=attachments)
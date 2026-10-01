# Copyright (c) 2026, Shayona Technology and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


DOCTYPE = "Customer Service Credential"
UNIQUE_CONSTRAINT = "unique_credential_type_account_name"


class CustomerServiceCredential(Document):
    def validate(self) -> None:
        self._normalize_fields()
        self._validate_unique_credential_account()

    def _normalize_fields(self) -> None:
        if isinstance(self.domain_name, str):
            self.domain_name = self.domain_name.strip().lower()

        if isinstance(self.account_name, str):
            self.account_name = self.account_name.strip()

        if isinstance(self.account_identity, str):
            self.account_identity = self.account_identity.strip() or None

        if isinstance(self.username, str):
            self.username = self.username.strip()

    def _validate_unique_credential_account(self) -> None:
        if not self.credential_type or not self.account_name:
            return

        filters: dict[str, object] = {
            "credential_type": self.credential_type,
            "account_name": self.account_name,
        }
        if self.name:
            filters["name"] = ["!=", self.name]

        duplicate = frappe.db.exists(DOCTYPE, filters)
        if duplicate:
            frappe.throw(
                _(
                    "A {0} credential with Account Name {1} already exists as {2}."
                ).format(
                    frappe.bold(self.credential_type),
                    frappe.bold(self.account_name),
                    frappe.bold(duplicate),
                ),
                title=_("Duplicate Credential Account"),
            )


def on_doctype_update() -> None:
    """Enforce the composite uniqueness rule at the database layer as well."""
    frappe.db.add_unique(
        DOCTYPE,
        ["credential_type", "account_name"],
        constraint_name=UNIQUE_CONSTRAINT,
    )

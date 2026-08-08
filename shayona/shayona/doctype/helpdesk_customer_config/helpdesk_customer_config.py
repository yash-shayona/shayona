# Copyright (c) 2026, Yash Solanki and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class HelpdeskCustomerConfig(Document):
    def validate(self):
        self._normalize_admin_users()
        self._validate_active_config()
        self._dedupe_allowed_templates()

    def _normalize_admin_users(self):
        seen = set()
        normalized_rows = []

        for row in self.admin_users or []:
            user = (row.user or "").strip()
            if not user:
                continue
            if user in seen:
                continue
            seen.add(user)
            normalized_rows.append({"user": user})

        # Backward compatibility for old single-admin field
        legacy_user = (self.admin_user or "").strip()
        if legacy_user and legacy_user not in seen:
            normalized_rows.append({"user": legacy_user})
            seen.add(legacy_user)

        self.set("admin_users", [])
        for row in normalized_rows:
            self.append("admin_users", row)

        # Keep legacy field populated during transition
        self.admin_user = normalized_rows[0]["user"] if normalized_rows else None

    def _get_admin_users(self) -> list[str]:
        return [(row.user or "").strip() for row in (self.admin_users or []) if row.user]

    def _validate_active_config(self):
        templates = [d.template for d in (self.allowed_templates or []) if d.template]
        admin_users = self._get_admin_users()

        if self.active and not admin_users:
            frappe.throw(_("At least one Admin User is required when config is active."))

        if self.active and not templates:
            frappe.throw(_("At least one Allowed Template is required when config is active."))

    def _dedupe_allowed_templates(self):
        seen = set()
        unique_rows = []

        for row in self.allowed_templates or []:
            template = (row.template or "").strip()
            if not template:
                continue

            if template in seen:
                frappe.throw(
                    _("Duplicate template in Allowed Templates: {0}").format(template)
                )

            seen.add(template)
            unique_rows.append(row)

        self.allowed_templates = unique_rows
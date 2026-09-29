from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class TwilioWhatsAppTemplate(Document):
    def validate(self):
        self.template_name = (self.template_name or "").strip()
        self.content_sid = (self.content_sid or "").strip()
        self.language_code = (self.language_code or "").strip()
        self.parameter_count = max(cint(self.parameter_count), 0)

        if not self.template_name:
            frappe.throw(_("Template Name is required."))

        if not self.content_sid:
            frappe.throw(_("Content SID is required."))

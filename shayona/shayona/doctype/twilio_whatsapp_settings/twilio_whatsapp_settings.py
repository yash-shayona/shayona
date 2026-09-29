from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class TwilioWhatsAppSettings(Document):
    def validate(self):
        self.account_sid = (self.account_sid or "").strip()
        self.whatsapp_from_number = (self.whatsapp_from_number or "").strip()
        self.default_country_code = (self.default_country_code or "").strip().upper()
        self.request_timeout_seconds = max(cint(self.request_timeout_seconds) or 15, 5)

        if not self.enabled:
            return

        if not self.account_sid:
            frappe.throw(_("Account SID is required when Twilio WhatsApp is enabled."))

        if not self.get_password("auth_token", raise_exception=False):
            frappe.throw(_("Auth Token is required when Twilio WhatsApp is enabled."))

        if not self.whatsapp_from_number:
            frappe.throw(_("WhatsApp From Number is required when Twilio WhatsApp is enabled."))

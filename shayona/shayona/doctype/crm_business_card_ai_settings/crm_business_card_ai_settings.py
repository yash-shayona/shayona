import frappe
from frappe import _
from frappe.model.document import Document


class CRMBusinessCardAISettings(Document):
    def validate(self):
        if self.request_timeout_sec and int(self.request_timeout_sec) < 10:
            frappe.throw(_("Request timeout must be at least 10 seconds."))

        if self.enabled:
            if not (self.twilio_whatsapp_template_sid or "").strip():
                frappe.throw(_("Twilio Template SID is required when settings are enabled."))

            if not _is_valid_whatsapp_number(self.twilio_whatsapp_from_number):
                frappe.throw(_("Registered WhatsApp Number must be a valid international number, e.g. +919876543210"))


def _is_valid_whatsapp_number(number):
    if not number:
        return False
    value = str(number).strip()
    if not value.startswith("+"):
        return False
    digits = "".join(ch for ch in value if ch.isdigit())
    return len(digits) >= 10

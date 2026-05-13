import frappe
from shayona.api.whatsapp_message import send_lead_whatsapp_followup


def send_application_lead_followup(doc, method=None):
    """
    Trigger WhatsApp follow-up only when lead source is 'Application'.
    Designed as a doc_event hook on CRM Lead after_insert.
    """
    try:
        source = (getattr(doc, "source", None) or "").strip().lower()
        if source != "application":
            return

        send_lead_whatsapp_followup(lead=doc, extracted={})
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Lead Followup Service Error")

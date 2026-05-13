
import json

import frappe
from twilio.rest import Client

FOLLOWUP_SOURCE_FIELD = "ai_business_card_followup"
TWILIO_TEMPLATE_VARIABLES = {}


def send_lead_whatsapp_followup(lead, extracted=None):
    extracted = extracted or {}
    to_number = _get_target_number(lead, extracted)

    if not to_number:
        return _result(
            status="prepared",
            to_number=None,
            reason="missing_mobile_number",
            source=f"{FOLLOWUP_SOURCE_FIELD}_missing_number",
        )

    settings = _get_twilio_settings()
    if not settings.get("ok"):
        return _result(
            status="prepared",
            to_number=to_number,
            reason=settings.get("reason"),
            source=f"{FOLLOWUP_SOURCE_FIELD}_template",
        )

    try:
        client = Client(settings["account_sid"], settings["auth_token"])
        payload = {
            "from_": f"whatsapp:{settings['from_number']}",
            "to": f"whatsapp:{to_number}",
            "content_sid": settings["content_sid"],
        }
        if TWILIO_TEMPLATE_VARIABLES:
            payload["content_variables"] = json.dumps(TWILIO_TEMPLATE_VARIABLES)

        twilio_message = client.messages.create(**payload)

        return _result(
            status="sent",
            to_number=to_number,
            sid=twilio_message.sid,
            channel_mode="template_only",
            source=f"{FOLLOWUP_SOURCE_FIELD}_template",
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Lead WhatsApp Template Send Error")
        return _result(
            status="failed",
            to_number=to_number,
            reason="twilio_send_failed",
            source=f"{FOLLOWUP_SOURCE_FIELD}_template",
        )


def _get_target_number(lead, extracted):
    possible_numbers = [
        extracted.get("mobile_no"),
        extracted.get("phone"),
        lead.get("custom_whatsapp") if lead else None,
        lead.get("mobile_no") if lead else None,
        lead.get("phone") if lead else None,
    ]

    for number in possible_numbers:
        formatted = _format_whatsapp_number(number)
        if formatted:
            return formatted

    return None


def _format_whatsapp_number(number):
    if not number:
        return None

    number = str(number).strip()
    has_plus = number.startswith("+")
    digits = "".join(ch for ch in number if ch.isdigit())
    if not digits:
        return None

    if has_plus:
        return f"+{digits}"

    if len(digits) == 10:
        country_code = str(frappe.conf.get("twilio_whatsapp_default_country_code")
            or "91"
        ).lstrip("+")
        return f"+{country_code}{digits}"

    if len(digits) > 10:
        return f"+{digits}"

    return None


def _get_twilio_settings():
    account_sid = auth_token = None

    content_sid, from_number = _get_business_card_twilio_config()
    from_number = _format_whatsapp_number(from_number)

    if frappe.db.exists("DocType", "CRM Twilio Settings"):
        twilio_settings = frappe.get_cached_doc("CRM Twilio Settings", "CRM Twilio Settings")
        if getattr(twilio_settings, "enabled", 0):
            account_sid = (getattr(twilio_settings, "account_sid", None) or "").strip()
            auth_token = twilio_settings.get_password("auth_token")

    if not account_sid:
        account_sid = ( frappe.conf.get("twilio_account_sid") or "").strip()
    if not auth_token:
        auth_token = (frappe.conf.get("twilio_auth_token") or "").strip()

    if not account_sid or not auth_token:
        return {"ok": False, "reason": "twilio_credentials_missing"}
    if not from_number:
        return {"ok": False, "reason": "twilio_whatsapp_from_missing"}
    if not content_sid:
        return {"ok": False, "reason": "twilio_whatsapp_template_sid_missing"}

    return {
        "ok": True,
        "account_sid": account_sid,
        "auth_token": auth_token,
        "from_number": from_number,
        "content_sid": content_sid,
    }


def _get_business_card_twilio_config():
    content_sid = ""
    from_number = ""

    if frappe.db.exists("DocType", "CRM Business Card AI Settings"):
        settings = frappe.get_cached_doc("CRM Business Card AI Settings", "CRM Business Card AI Settings")
        content_sid = (getattr(settings, "twilio_whatsapp_template_sid", None) or "").strip()
        from_number = (getattr(settings, "twilio_whatsapp_from_number", None) or "").strip()

    if not content_sid:
        content_sid = ( frappe.conf.get("twilio_whatsapp_template_sid")
            or ""
        ).strip()

    if not from_number:
        from_number = (frappe.conf.get("twilio_whatsapp_from_number")
            or ""
        ).strip()

    return content_sid, from_number


def _result(status, to_number, source=None, **extra):
    payload = {
        "status": status,
        "to": to_number,
    }
    if source:
        payload["source"] = source
    payload.update(extra)
    return payload

from __future__ import annotations

import json
import logging

import frappe
import phonenumbers
import requests
from frappe import _
from frappe.utils import cint

TWILIO_MESSAGES_URL = (
    "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
)


def enqueue_template_message(
    *,
    to: str,
    content_sid: str,
    content_variables: dict[str, str],
    notification_name: str | None = None,
    reference_doctype: str | None = None,
    reference_name: str | None = None,
) -> None:
    """
    Queue Twilio delivery only after the current DB transaction commits.

    Recipient and template values are already resolved before this
    function is called.

    Actual external HTTP request runs in a Frappe RQ worker, so the
    Desk/API request that created the source document does not wait
    for Twilio.
    """

    frappe.enqueue(
        (
            "shayona.integrations.twilio."
            "send_template_message_job"
        ),
        queue="short",
        enqueue_after_commit=True,
        to=to,
        content_sid=content_sid,
        content_variables=dict(content_variables),
        notification_name=notification_name,
        reference_doctype=reference_doctype,
        reference_name=reference_name,
    )


def send_template_message_job(
    *,
    to: str,
    content_sid: str,
    content_variables: dict[str, str],
    notification_name: str | None = None,
    reference_doctype: str | None = None,
    reference_name: str | None = None,
) -> dict:
    """
    Background worker entry point for a queued
    WhatsApp template send.
    """

    result = send_template_message(
        to=to,
        content_sid=content_sid,
        content_variables=content_variables,
    )

    logger = frappe.logger("twilio_whatsapp_notification")
    logger.setLevel(logging.INFO)
    logger.info(
        ("Sent WhatsApp Notification %s for %s %s " "to %s; Twilio SID=%s status=%s"),
        notification_name or "(unknown)",
        reference_doctype or "(unknown)",
        reference_name or "(unknown)",
        to,
        result.get("sid"),
        result.get("status"),
    )

    return result


def send_template_message(
    *, to: str, content_sid: str, content_variables: dict[str, str]
) -> dict:
    settings = _get_settings()

    account_sid = (settings.account_sid or "").strip()
    auth_token = settings.get_password("auth_token", raise_exception=False)
    from_number = _normalize_phone_number(
        settings.whatsapp_from_number,
        default_region=settings.default_country_code,
    )
    to_number = _normalize_phone_number(
        to,
        default_region=settings.default_country_code,
    )

    if not account_sid or not auth_token:
        frappe.throw(_("Twilio Account SID and Auth Token are required."))

    payload = {
        "From": f"whatsapp:{from_number}",
        "To": f"whatsapp:{to_number}",
        "ContentSid": (content_sid or "").strip(),
        "ContentVariables": json.dumps(
            content_variables, separators=(",", ":"), ensure_ascii=False
        ),
    }

    timeout = max(cint(settings.request_timeout_seconds) or 15, 5)
    url = TWILIO_MESSAGES_URL.format(account_sid=account_sid)

    try:
        response = requests.post(
            url,
            auth=(account_sid, auth_token),
            data=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise frappe.ValidationError(
            _("Unable to reach Twilio: {0}").format(str(exc))
        ) from exc

    try:
        response_data = response.json()
    except ValueError:
        response_data = {"message": response.text[:1000]}

    if not response.ok:
        error_message = response_data.get("message") or _(
            "Twilio returned HTTP {0}"
        ).format(response.status_code)
        error_code = response_data.get("code")
        if error_code:
            error_message = _("Twilio error {0}: {1}").format(error_code, error_message)

        raise frappe.ValidationError(error_message)

    return {
        "sid": response_data.get("sid"),
        "status": response_data.get("status"),
        "to": response_data.get("to"),
    }


def _get_settings():
    settings = frappe.get_cached_doc("Twilio WhatsApp Settings")
    if not settings.enabled:
        frappe.throw(_("Twilio WhatsApp Settings are disabled."))
    return settings


def _normalize_phone_number(
    number: str | None, default_region: str | None = None
) -> str:
    raw_number = (number or "").strip()
    if not raw_number:
        frappe.throw(_("WhatsApp recipient number is empty."))

    if raw_number.lower().startswith("whatsapp:"):
        raw_number = raw_number.split(":", 1)[1].strip()

    region = (default_region or "").strip().upper() or None

    if not raw_number.startswith("+") and not region:
        frappe.throw(
            _(
                "Phone number {0} is not in E.164 format and no Default Country Code is configured."
            ).format(frappe.bold(raw_number))
        )

    try:
        parsed = phonenumbers.parse(raw_number, region)
    except phonenumbers.NumberParseException as exc:
        raise frappe.ValidationError(
            _("Invalid phone number {0}: {1}").format(raw_number, str(exc))
        ) from exc

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(
        parsed
    ):
        frappe.throw(_("Invalid phone number: {0}").format(frappe.bold(raw_number)))

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)

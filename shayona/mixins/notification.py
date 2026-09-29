from __future__ import annotations

import logging

import frappe
from frappe import _
from frappe.utils import cint

from shayona.integrations.twilio import send_template_message, enqueue_template_message


class NotificationWhatsAppMixin:
    """Adds a Twilio WhatsApp template channel to Frappe's standard Notification."""

    def validate(self):
        super().validate()

        if self.channel != "WhatsApp":
            return

        self._validate_whatsapp_configuration()

    def send_notification_by_channel(self, doc, context):
        if self.channel != "WhatsApp":
            return super().send_notification_by_channel(doc, context)

        try:
            self._send_whatsapp_template(doc, context)
        except Exception:
            # Match Frappe Notification's behavior: log channel delivery errors
            # instead of breaking the source document transaction.
            self.log_error("Failed to send WhatsApp Notification")

    def _validate_whatsapp_configuration(self):
        if not frappe.db.get_single_value("Twilio WhatsApp Settings", "enabled"):
            frappe.throw(
                _(
                    "Enable Twilio WhatsApp Settings before enabling a WhatsApp Notification."
                )
            )

        template_name = self.get("custom_whatsapp_template")
        if not template_name:
            frappe.throw(_("Select a Twilio WhatsApp Template."))

        template = frappe.get_cached_doc("Twilio WhatsApp Template", template_name)

        if not template.enabled:
            frappe.throw(
                _("Twilio WhatsApp Template {0} is disabled.").format(
                    frappe.bold(template.name)
                )
            )

        if (
            template.reference_doctype
            and template.reference_doctype != self.document_type
        ):
            frappe.throw(
                _(
                    "Template {0} is restricted to {1}, but this Notification uses {2}."
                ).format(
                    frappe.bold(template.name),
                    frappe.bold(template.reference_doctype),
                    frappe.bold(self.document_type),
                )
            )

        if self.send_system_notification:
            frappe.throw(
                _(
                    "Send System Notification is not supported for the WhatsApp channel in this MVP."
                )
            )

        if self.attach_print or self.attach_files:
            frappe.throw(
                _("Attachments are not supported for the WhatsApp channel in this MVP.")
            )

        variables = self.get("custom_whatsapp_variables") or []
        expected_count = cint(template.parameter_count)

        variable_numbers = [cint(row.variable_no) for row in variables]
        if any(number <= 0 for number in variable_numbers):
            frappe.throw(_("WhatsApp variable numbers must start from 1."))

        if len(variable_numbers) != len(set(variable_numbers)):
            frappe.throw(_("WhatsApp variable numbers cannot be duplicated."))

        expected_numbers = list(range(1, expected_count + 1))
        if sorted(variable_numbers) != expected_numbers:
            frappe.throw(
                _("Template {0} expects variable numbers {1}.").format(
                    frappe.bold(template.name),
                    ", ".join(str(number) for number in expected_numbers) or _("none"),
                )
            )

        for row in variables:
            if not row.value_template:
                frappe.throw(
                    _("Set a value for WhatsApp variable {0}.").format(row.variable_no)
                )

    def _send_whatsapp_template(self, doc, context):
        template = frappe.get_cached_doc(
            "Twilio WhatsApp Template",
            self.get("custom_whatsapp_template"),
        )

        receivers = self.get_receiver_list(doc, context)
        if not receivers:
            return

        content_variables = self._render_whatsapp_variables(context)

        for receiver in receivers:
            enqueue_template_message(
                to=receiver,
                content_sid=template.content_sid,
                content_variables=content_variables,
                notification_name=self.name,
                reference_doctype=doc.doctype,
                reference_name=doc.name,
            )

            logger = frappe.logger("twilio_whatsapp_notification")
            logger.setLevel(logging.INFO)
            logger.info(
                ("Queued WhatsApp Notification %s " "for %s %s to %s after commit"),
                self.name,
                doc.doctype,
                doc.name,
                receiver,
            )

    def _render_whatsapp_variables(self, context):
        variables = {}

        for row in sorted(
            self.get("custom_whatsapp_variables") or [],
            key=lambda item: cint(item.variable_no),
        ):
            rendered_value = frappe.render_template(row.value_template or "", context)
            variables[str(cint(row.variable_no))] = str(rendered_value)

        return variables

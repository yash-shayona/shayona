import frappe
from frappe.utils import get_url_to_form

ALERT_NOTIFICATION_TYPE = "Alert"
REALTIME_ALERT_EVENT_NAME = "shayona_alert_popup"


def publish_alert_popup_event(notification_log_doc, method=None):
    """Publish realtime popup event when an Alert notification is created.

    This function is called from `Notification Log.after_insert` hook.
    """
    if not should_publish_popup(notification_log_doc):
        return

    frappe.publish_realtime(
        REALTIME_ALERT_EVENT_NAME,
        message=build_realtime_payload(notification_log_doc),
        user=notification_log_doc.for_user,
        after_commit=True,
    )


def should_publish_popup(notification_log_doc):
    """Allow popup only for valid user-targeted Alert notifications."""
    if not notification_log_doc:
        return False

    if not notification_log_doc.for_user:
        return False

    if notification_log_doc.type != ALERT_NOTIFICATION_TYPE:
        return False

    return True


def build_realtime_payload(notification_log_doc):
    """Keep realtime payload creation in one place for easier maintenance."""
    return {
        "name": notification_log_doc.name,
        "subject": notification_log_doc.subject,
        "document_type": notification_log_doc.document_type,
        "document_name": notification_log_doc.document_name,
        "link": resolve_notification_link(notification_log_doc),
        "creation": str(notification_log_doc.creation) if notification_log_doc.creation else None,
    }


def resolve_notification_link(notification_log_doc):
    """Use explicit link if available, else build form URL from doctype/docname."""
    if notification_log_doc.link:
        return notification_log_doc.link

    if notification_log_doc.document_type and notification_log_doc.document_name:
        return get_url_to_form(notification_log_doc.document_type, notification_log_doc.document_name)

    return None


@frappe.whitelist()
def get_unread_notification_count():
    """Return unread Notification Log count for current user."""
    if frappe.session.user == "Guest":
        return 0

    return frappe.db.count(
        "Notification Log",
        filters={"for_user": frappe.session.user, "read": 0},
    )

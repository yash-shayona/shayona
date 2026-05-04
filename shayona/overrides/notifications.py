import frappe
from frappe.utils import get_url_to_form


def publish_alert_popup_event(doc, method=None):
    """Publish a dedicated realtime event for alert notifications."""
    if not doc.for_user or doc.type != "Alert":
        return

    link = doc.link
    if not link and doc.document_type and doc.document_name:
        link = get_url_to_form(doc.document_type, doc.document_name)

    frappe.publish_realtime(
        "shayona_alert_popup",
        message={
            "name": doc.name,
            "subject": doc.subject,
            "document_type": doc.document_type,
            "document_name": doc.document_name,
            "link": link,
            "creation": str(doc.creation) if doc.creation else None,
        },
        user=doc.for_user,
        after_commit=True,
    )


@frappe.whitelist()
def get_unread_notification_count():
    if frappe.session.user == "Guest":
        return 0

    return frappe.db.count("Notification Log", filters={"for_user": frappe.session.user, "read": 0})


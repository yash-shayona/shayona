import json

import frappe

from shayona.services.aes_decrypt import get_activity_tracker_key_b64
from shayona.services.tracker_processor import enqueue_activity_upload


@frappe.whitelist()
def get_tracker_key():
    return {"key": get_activity_tracker_key_b64()}


@frappe.whitelist()
def receive_activity():
    user_id = frappe.form_dict.get("user_id")
    if not user_id:
        return {"status": False, "message": "Missing user_id"}

    if not frappe.db.exists("User", user_id):
        return {"status": False, "message": "Invalid user_id"}

    request_files = frappe.local.request.files
    event_files = sorted(
        [(key, value) for key, value in request_files.items() if key.startswith("events_file_")],
        key=lambda item: item[0],
    )
    screenshot_files = sorted(
        [(key, value) for key, value in request_files.items() if key.startswith("screenshot_")],
        key=lambda item: item[0],
    )

    screenshots_meta_raw = frappe.form_dict.get("screenshots_meta") or "[]"
    try:
        screenshots_meta = json.loads(screenshots_meta_raw)
        if not isinstance(screenshots_meta, list):
            screenshots_meta = []
    except ValueError:
        screenshots_meta = []

    if not event_files and not screenshot_files:
        return {"status": False, "message": "Missing upload files"}

    try:
        upload_id = enqueue_activity_upload(
            user_id=user_id,
            event_files=event_files,
            screenshot_files=screenshot_files,
            screenshots_meta=screenshots_meta,
        )
        return {
            "status": True,
            "queued": True,
            "upload_id": upload_id,
        }
    except Exception as exc:
        frappe.log_error(frappe.get_traceback(), "ACTIVITY TRACKER ERROR")
        return {
            "status": False,
            "message": str(exc),
        }


@frappe.whitelist()
def report_error():
    payload = frappe.form_dict
    device_name = payload.get("device_name") or "Unknown device"
    message = payload.get("message") or "Unknown tracker error"
    missing_fields = payload.get("missing_fields")

    if missing_fields:
        if isinstance(missing_fields, str):
            missing_fields = [missing_fields]
        message += f"<br>Missing fields: {', '.join(missing_fields)}"

    try:
        frappe.sendmail(
            recipients=["yashsolanki@shayonatechnology.com"],
            subject=f"Activity Tracker Error: {device_name}",
            message=message,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "ACTIVITY TRACKER ERROR")

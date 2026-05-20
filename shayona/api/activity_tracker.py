import frappe
import base64
import json
from shayona.services.tracker_processor import process_activity_upload

@frappe.whitelist()
def get_tracker_key():
    key = frappe.get_site_config().get("activity_tracker_key_b64")
    return {"key": key}

@frappe.whitelist()
def receive_activity():
    """Main endpoint to receive activity tracker upload."""
    
    user_id = frappe.form_dict.get("user_id")
    if not user_id:
        return {
            "status": False, 
            "message": "Missing user_id"
        }
    elif not frappe.db.exists("User", user_id):
        return {
            "status": False, 
            "message": "Invalid user_id"
        }

    files = frappe.local.request.files

    # collect all event files
    event_files = [
        f for k, f in files.items()
        if k.startswith("events_file_")
    ]
    
    if not event_files:
        return {
            "status": False, 
            "message": "Missing events_file"
        }

    screenshot = files.get("screenshot")  # optional

    last_tracker = None

    try:
        for f in event_files:
            try:
                payload = json.load(f)
            except UnicodeDecodeError as e:
                continue
            except json.JSONDecodeError as e:
                continue
            
            last_tracker = process_activity_upload(
                user_id=user_id,
                payload=payload,
                screenshot_file=screenshot  # screenshot only once
            )

        return {
            "status": True, 
            "activity_tracker": last_tracker
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ACTIVITY TRACKER ERROR")
        return {
            "status": False,
            "message": str(e)
        }
        
@frappe.whitelist()
def report_error():
    payload = frappe.form_dict
    
    # extract payload
    device_name = payload.get("device_name")
    message = payload.get("message")
    missing_fields = payload.get("missing_fields")
    
    if missing_fields:
        message += f"<br>Missing fields: {', '.join(missing_fields)}"
    
    try:
        frappe.sendmail(
            recipients=["yashsolanki@shayonatechnology.com"],
            subject=f"Activity Tracker Error: {device_name}",
            message=message
        )
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "ACTIVITY TRACKER ERROR")
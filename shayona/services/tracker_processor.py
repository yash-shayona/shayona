import json
import frappe
from frappe.utils.file_manager import save_file, save_file_on_filesystem
from shayona.services.aes_decrypt import decrypt_payload
from frappe.utils import get_datetime

def get_or_create_tracker(user_id, date):
    """Find Activity Tracker record by user or create one."""
    
    # Resolve user
    user = user_id if frappe.db.exists("User", user_id) else frappe.get_value("User", {"name": user_id})
      
    # check if employee exists  
    emp = frappe.get_value("Employee", {"user_id": user}, "name")
    
    # check if timesheet exists
    timesheet = frappe.get_value("Timesheet", {"employee": emp, "start_date": frappe.utils.nowdate()}, "name")
    
    filters = {"user": user or user_id, "date": date}
    
    tracker_name = frappe.get_value(
                        "Activity Tracker", 
                        filters, 
                        ["name", "employee", "timesheet"],
                        as_dict=True
                    )

    if tracker_name:
        # if not employee link in existing doc than link it
        if not tracker_name.employee:
            frappe.db.set_value("Activity Tracker", tracker_name.name, "employee", emp)
            
        # if not timesheet link in existing doc than link it
        if not tracker_name.timesheet:
            frappe.db.set_value("Activity Tracker", tracker_name.name, "timesheet", timesheet)
        
        return frappe.get_doc("Activity Tracker", tracker_name.name)
    else:
        doc = frappe.get_doc({
            "doctype": "Activity Tracker",
            "user": user,
            "employee": emp or None,
            "date": date,
            "timesheet": timesheet,
            "total_idle_time_hrs": 0,
            "total_idle_time_mins": 0,
            "activity_tracker_detail": []
        })
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        return doc

def process_activity_upload(user_id, payload, screenshot_file):
    """Decrypt events, create child rows, attach screenshot."""
    
    plaintext = decrypt_payload(payload)
    # print("plaintext", plaintext)
    events = json.loads(plaintext)   # list of event objects

    last_child = None
    last_tracker = None  # to attach screenshot later
    
    tracker_map = {}

    for ev in events:
        event_date = ev.get("date")
        
        tracker = tracker_map.get(event_date)
        if not tracker:
            tracker = get_or_create_tracker(user_id, event_date)
            tracker_map[event_date] = tracker
            
        timestamp = ev.get("timestamp")
        active_window = ev.get("active_window", "")
        idle_sec = float(ev.get("idle_seconds", 0))
        mouse = ev.get("mouse_presses", 0)
        keyboard = ev.get("keyboard_presses", 0)
        event_id = ev.get("event_id", "")
        
        if frappe.db.exists(
            "Activity Tracker Detail",
            {
                "parent": tracker.name,
                "event_id": event_id
            }):
            continue

        last_child = tracker.append("activity_tracker_detail", {
            "active_window": active_window,
            "idle_time_sec": idle_sec,
            "mouse_count": mouse,
            "keyboard_count": keyboard,
            "timestamp": timestamp,
            "event_id": event_id
        })

        tracker.total_idle_time_hrs += float(ev.get("idle_seconds", 0)) / 3600
        tracker.total_idle_time_mins += float(ev.get("idle_seconds", 0)) / 60
        last_tracker = tracker
        
    # 🔐 SAVE ONCE PER TRACKER
    for tracker in tracker_map.values():
        tracker.save()
        
    frappe.db.commit()

    # Attach screenshot (if provided) to last child row
    if screenshot_file and last_child and last_tracker:
        st_ts = frappe.form_dict.get("st_ts")
        
        filename = screenshot_file.filename or "screenshot.png"
        content = screenshot_file.read()
        saved = save_file(
            filename,
            content, 
            "Activity Tracker", 
            last_tracker.name, 
            is_private=1
        )

        # add file url in child row (make sure you added this field)
        last_child.screenshot = saved.file_url
        last_child.st_ts = st_ts
        last_tracker.save()
        frappe.db.commit()

    return last_tracker.name if last_tracker else None

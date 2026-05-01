import frappe
from frappe.utils import getdate, get_datetime
from datetime import time

def validate(doc, method):
    check_timesheet_exists(doc)
    can_not_add_manual_time_log_entry(doc)

def before_insert(doc, method):
    set_timesheet_day(doc)

def before_save(doc, method):
    calculate_total_break_hours(doc)

def before_submit(doc, method):
    if not doc.custom_auto_submit or doc.custom_auto_submit != "Yes":
        doc.custom_auto_submit = "No"

def check_timesheet_exists(doc):
    ts_date = getdate(doc.start_date or doc.start_time)

    exists = frappe.db.exists(
        "Timesheet",
        {
            "employee": doc.employee,
            "start_date": ts_date,
            "name": ["!=", doc.name],  # ignore same doc
            "docstatus": ["!=", 2]
        }
    )

    if exists:
        frappe.throw(
            f"Timesheet already exists for employee <b>{doc.employee_name}</b> on date <b>{ts_date.__format__('%d-%m-%Y')}</b>."
        )

def set_timesheet_day(doc):
    if not doc.get("custom_day"):
        doc.custom_day = getdate(doc.start_date).strftime("%A")
        print(doc.as_dict())

def calculate_total_break_hours(doc):
    custom_total_break_hours = 0
    for time_log in doc.time_logs:
        if time_log.activity_type == "Break":
            custom_total_break_hours += time_log.hours or 0

    doc.custom_total_break_hours = custom_total_break_hours

def can_not_add_manual_time_log_entry(doc):
    allowed_roles = ["System Manager", "HR Manager", "Administrator"]

    if not any(frappe.has_role(role) for role in allowed_roles):
        for row in doc.time_logs:
            if row.is_manual_entry:
                frappe.throw("Employees cannot manually add time log entries.")

def auto_submit_timesheet():
    today = getdate()
    
    timesheets = frappe.get_all(
        "Timesheet",
        fields=["name", "status", "employee", "employee_name"],
        filters={
            "start_date": today,
            "docstatus": 0
        }
    )

    for ts in timesheets:
        doc = frappe.get_doc("Timesheet", ts.name)
        
        for log in doc.time_logs:
            if log.from_time and not log.to_time:
                log.to_time = get_datetime()
                log.completed = 1

        doc.custom_auto_submit = "Yes"

        try:
            doc.save(ignore_permissions=True)
            doc.submit()
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(frappe.get_traceback(), f"Auto Submit Timesheet Failed: {doc.name}")
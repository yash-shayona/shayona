import frappe
from frappe.utils import getdate

def validate(doc, method):
    check_timesheet_exists(doc)

def before_insert(doc, method):
    set_timesheet_day(doc)

def before_save(doc, method):
    calculate_total_break_hours(doc)

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
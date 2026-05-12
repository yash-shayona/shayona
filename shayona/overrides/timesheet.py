import frappe
from frappe.utils import getdate, get_datetime
from datetime import time
from erpnext.projects.doctype.timesheet.timesheet import Timesheet
from shayona.overrides.task import is_regency


class CustomTimesheet(Timesheet):
    def update_task_and_project(self):
        tasks, projects = [], []

        for data in self.time_logs:

            # -----------------------------
            # TASK UPDATE
            # -----------------------------
            if data.task and data.task not in tasks:

                task = frappe.get_doc("Task", data.task)

                # ERPNext original logic
                task.update_time_and_costing()

                # Check all time logs completed
                time_logs_completed = all(
                    tl.completed for tl in self.time_logs if tl.task == task.name
                )

                # -----------------------------------------
                # CUSTOM LOGIC FOR REGENCY PROJECTS
                # -----------------------------------------
                if is_regency(task):
                    pass
                else:
                    # ERPNext default behavior
                    if time_logs_completed:
                        task.status = "Completed"
                    else:
                        task.status = "Working"

                # -----------------------------------------
                # PASS CUSTOM FLAG
                # -----------------------------------------
                task.flags.from_timesheet = True

                # Save task
                task.save(ignore_permissions=True)

                tasks.append(data.task)

            # -----------------------------
            # PROJECT TRACKING
            # -----------------------------
            if data.project and data.project not in projects:
                projects.append(data.project)

        # -----------------------------
        # PROJECT UPDATE
        # -----------------------------
        for project in projects:
            project_doc = frappe.get_doc("Project", project)

            # ERPNext original logic
            project_doc.update_project()

            project_doc.save(ignore_permissions=True)


def validate(doc, method):
    check_timesheet_exists(doc)
    check_employee_set_or_not(doc)
    allow_timer_start_end(doc)


def before_insert(doc, method):
    set_timesheet_day(doc)
    set_company(doc)


def before_save(doc, method):
    calculate_total_break_hours(doc)


def before_submit(doc, method):
    set_auto_submit_flag(doc)
    calculate_break_adjustment(doc)


def set_auto_submit_flag(doc):
    if not doc.custom_auto_submit or doc.custom_auto_submit != "Yes":
        doc.custom_auto_submit = "No"


def calculate_break_adjustment(doc):
    IDEAL_BREAK = 35 / 60  # 0.5833 hr

    total_hours = doc.total_hours or 0

    # If no working hours, don't apply any break deduction
    if total_hours <= 0:
        doc.custom_total_break_hours = 0
        doc.custom_total_effective_hours = 0
        return

    total_break = 0

    for row in doc.time_logs:
        if row.activity_type == "Break":
            total_break += row.hours or 0

    actual_work = total_hours - total_break

    # only breaks logged
    if actual_work <= 0:
        doc.custom_total_break_hours = total_break
        doc.custom_total_effective_hours = 0
        return

    if total_break == 0:
        # No break logged → no deduction
        doc.custom_total_break_hours = 0
        effective_hours = total_hours
    else:
        # Break logged → adjust based on deviation from ideal
        doc.custom_total_break_hours = total_break
        effective_hours = total_hours + (IDEAL_BREAK - total_break)

    doc.custom_total_effective_hours = max(effective_hours, 0)


def check_employee_set_or_not(doc):
    if not doc.employee:
        frappe.throw("Employee must be selected.")


def allow_timer_start_end(doc):
    allowed_start = time(8, 30)
    allowed_end = time(20, 30)

    for tl in doc.time_logs:
        if not tl.from_time:
            continue

        from_dt = get_datetime(tl.from_time)
        if not from_dt:
            continue

        from_time = from_dt.time()
        if from_time < allowed_start:
            frappe.throw("You cannot start the timer before 8:30 AM.")

        # Validate stop-time only when it is actually set.
        if tl.to_time:
            # Skip validation during auto submit
            if doc.custom_auto_submit == "Yes":
                continue

            to_dt = get_datetime(tl.to_time)
            if not to_dt:
                continue

            to_time = to_dt.time()
            if to_time > allowed_end:
                frappe.throw("You cannot stop the timer after 8:30 PM.")


def check_timesheet_exists(doc):
    ts_date = getdate(doc.start_date)

    exists = frappe.db.exists(
        "Timesheet",
        {
            "employee": doc.employee,
            "start_date": ts_date,
            "name": ["!=", doc.name],  # ignore same doc
            "docstatus": ["!=", 2],
        },
    )

    if exists:
        frappe.throw(
            f"Timesheet already exists for employee <b>{doc.employee_name}</b> on date <b>{ts_date.__format__('%d-%m-%Y')}</b>."
        )


def set_timesheet_day(doc):
    if not doc.get("custom_day"):
        doc.custom_day = getdate(doc.start_date).strftime("%A")
        print(doc.as_dict())


def set_company(doc):
    if not doc.company:
        company = frappe.db.get_value("Employee", doc.employee, "company")
        doc.company = company


def calculate_total_break_hours(doc):
    custom_total_break_hours = 0
    for time_log in doc.time_logs:
        if time_log.activity_type == "Break":
            custom_total_break_hours += time_log.hours or 0

    doc.custom_total_break_hours = custom_total_break_hours


def auto_submit_timesheet():
    today = getdate()

    timesheets = frappe.get_all(
        "Timesheet",
        fields=["name", "status", "employee", "employee_name"],
        filters={"start_date": today, "docstatus": 0},
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
        except Exception:
            frappe.log_error(
                frappe.get_traceback(), f"Auto Submit Timesheet Failed: {doc.name}"
            )

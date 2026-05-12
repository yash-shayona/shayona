import frappe
from frappe.utils import getdate, get_datetime
from datetime import time


class TimesheetMixin:
    def set_timesheet_day(self):
        if not self.get("custom_day"):
            self.custom_day = getdate(self.start_date).strftime("%A")

    def set_company(self):
        if not self.company:
            company = frappe.db.get_value("Employee", self.employee, "company")
            self.company = company

    def check_timesheet_exists(self):
        ts_date = getdate(self.start_date)

        exists = frappe.db.exists(
            "Timesheet",
            {
                "employee": self.employee,
                "start_date": ts_date,
                "name": ["!=", self.name],  # ignore same doc
                "docstatus": ["!=", 2],
            },
        )

        if exists:
            frappe.throw(
                f"Timesheet already exists for employee <b>{self.employee_name}</b> on date <b>{ts_date.__format__('%d-%m-%Y')}</b>."
            )

    def check_employee_set_or_not(self):
        if not self.employee:
            frappe.throw("Employee must be selected.")

    def allow_timer_start_end(self):
        allowed_start = time(8, 30)
        allowed_end = time(20, 30)

        for tl in self.time_logs:
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
                if self.custom_auto_submit == "Yes":
                    continue

                to_dt = get_datetime(tl.to_time)
                if not to_dt:
                    continue

                to_time = to_dt.time()
                if to_time > allowed_end:
                    frappe.throw("You cannot stop the timer after 8:30 PM.")

    def calculate_total_break_hours(self):
        custom_total_break_hours = 0
        for time_log in self.time_logs:
            if time_log.activity_type == "Break":
                custom_total_break_hours += time_log.hours or 0

        self.custom_total_break_hours = custom_total_break_hours

    def set_auto_submit_flag(self):
        if not self.custom_auto_submit or self.custom_auto_submit != "Yes":
            self.custom_auto_submit = "No"

    def calculate_break_adjustment(self):
        IDEAL_BREAK = 35 / 60  # 0.5833 hr

        total_hours = self.total_hours or 0

        # If no working hours, don't apply any break deduction
        if total_hours <= 0:
            self.custom_total_break_hours = 0
            self.custom_total_effective_hours = 0
            return

        total_break = 0

        for row in self.time_logs:
            if row.activity_type == "Break":
                total_break += row.hours or 0

        actual_work = total_hours - total_break

        # only breaks logged
        if actual_work <= 0:
            self.custom_total_break_hours = total_break
            self.custom_total_effective_hours = 0
            return

        if total_break == 0:
            # No break logged → no deduction
            self.custom_total_break_hours = 0
            effective_hours = total_hours
        else:
            # Break logged → adjust based on deviation from ideal
            self.custom_total_break_hours = total_break
            effective_hours = total_hours + (IDEAL_BREAK - total_break)

        self.custom_total_effective_hours = max(effective_hours, 0)


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

import frappe
from erpnext.projects.doctype.timesheet.timesheet import Timesheet


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
                if task.is_regency():
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
    doc.check_timesheet_exists()
    doc.check_employee_set_or_not()
    doc.allow_timer_start_end()


def before_insert(doc, method):
    doc.set_timesheet_day()
    doc.set_company()


def before_save(doc, method):
    doc.calculate_total_break_hours()


def before_submit(doc, method):
    doc.set_auto_submit_flag()
    doc.calculate_break_adjustment()

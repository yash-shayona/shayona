import frappe
from frappe.utils import get_datetime


class TaskMixin:
    def is_regency(self):
        """Check custom_project_type field exists and is 'regency'"""
        if not hasattr(self, "custom_project_type"):
            return False
        return (self.custom_project_type or "").lower() == "regency"

    def check_duplicate_subject(self):
        if not self.subject:
            return

        exists = frappe.db.exists(
            "Task",
            {
                "subject": self.subject,
                "name": ["!=", self.name],  # ignore current doc
            },
        )

        if exists:
            frappe.throw(
                title="Duplicate",
                msg="Task already exists.",
            )

    def check_custom_rbs_task_update_date(self):
        if not self.is_regency():
            return

        if self.custom_rbs_task and len(self.custom_rbs_task) > 0:
            if self.custom_rbs_task_update:
                for row in self.custom_rbs_task_update:
                    if row.task_update_date < self.custom_rbs_task[0].task_date:
                        frappe.throw("Task Update Date cannot be before Task Date")

    def validate_on_completed(self):
        """
        When task status = Completed:
        1. RBS Task row must have buyer_name, buyer_user_name, vibe_id
        2. All rows in RBS Task Update must have task_status = Completed
        """
        # Skip validation if status changed from Timesheet
        if getattr(self.flags, "from_timesheet", False):
            return

        if not self.is_regency():
            return

        if self.status != "Completed":
            return

        # --- Check 1: RBS Task required fields ---
        if not self.get("custom_rbs_task") or len(self.custom_rbs_task) == 0:
            frappe.throw(
                "RBS Task table must have at least one record to mark task as <b>Completed</b>."
            )

        rbs_row = self.custom_rbs_task[0]
        missing = []

        if not rbs_row.get("buyer_name"):
            missing.append("Buyer Name")
        if not rbs_row.get("buyer_user_name"):
            missing.append("Buyer User Name")
        if not rbs_row.get("vibe_id"):
            missing.append("Vibe ID")

        if missing:
            missing_list = "".join(f"<li><b>{field}</b></li>" for field in missing)

            frappe.throw(
                # f"Task: <b><a href='/desk/task/{self.name}'>{self.subject}</a></b><br>"
                f"Cannot mark task as <b>Completed</b>.<br><br>"
                f"First, Go to the <b><a href='/desk/task/{self.name}#custom_rbs_task_tab'>RBS Task</a></b> Tab in Tabbar.<br>"
                f"Please fill the following fields in RBS Task table:<br>"
                f"<ul>{missing_list}</ul>"
            )

        # --- Check 2: All update rows must be Completed + task_detail filled ---
        if self.get("custom_rbs_task_update"):
            errors = []

            for i, row in enumerate(self.custom_rbs_task_update):
                row_errors = []

                if row.task_status != "Completed":
                    row_errors.append(
                        f"Status is <b>{row.task_status or 'Not Set'}</b> (must be Completed)"
                    )

                if not row.get("task_detail"):
                    row_errors.append("Task Detail is empty (must be filled)")

                if row_errors:
                    errors.append(f"Row {i + 1}: " + " &amp; ".join(row_errors))

            if errors:
                frappe.throw(
                    # f"Task: <b><a href='/desk/task/{self.name}'>{self.subject}</a></b><br>"
                    f"Cannot mark task as <b>Completed</b>.<br><br>"
                    f"First, Go to the <b><a href='/desk/task/{self.name}#custom_rbs_task_update_tab'>RBS Task</a></b> Tab in Tabbar.<br>"
                    f"Please fix the following in RBS Task Update table:<br><br>"
                    + "<br>".join(errors)
                )

    def set_default_rbs_task_row(self):
        if not self.is_regency():
            return

        # Get today's date once
        today = get_datetime().date()

        if not self.get("custom_rbs_task"):
            self.append("custom_rbs_task", {"task_date": today})

        if (
            not self.get("custom_rbs_task_update")
            or len(self.custom_rbs_task_update) == 0
        ):
            self.append(
                "custom_rbs_task_update",
                {"task_update_date": today, "task_status": "Received"},
            )

        # If exactly 1 row
        if len(self.custom_rbs_task_update) == 1:
            row = self.custom_rbs_task_update[0]

            if not row.task_update_date or not row.task_status:
                row.task_update_date = today
                row.task_status = "Received"

    def set_default_rbs_task_update_row(self):
        if not self.is_regency():
            return

        if (
            not self.get("custom_rbs_task_update")
            or len(self.custom_rbs_task_update) == 0
        ):
            self.append(
                "custom_rbs_task_update",
                {"task_update_date": get_datetime().date(), "task_status": "Received"},
            )

    def handle_status_change_to_update_table(self):
        """
        When status changes from Completed → RTS Info Needed / Revisions Needed,
        auto-add a new row in RBS Task Update with the new status.
        """
        if self.is_new():
            return

        if not self.is_regency():
            return

        # Statuses that trigger a new update row
        tracked_statuses = ["RTS Info Needed", "Revisions Needed"]

        if self.status not in tracked_statuses:
            return

        # Get previous status from DB
        prev_status = frappe.db.get_value("Task", self.name, "status")

        if prev_status != "Completed":
            return

        # Check if a row with this status already added (avoid duplicates on re-save)
        already_exists = any(
            row.task_status == self.status for row in self.custom_rbs_task_update
        )

        if not already_exists:
            self.append(
                "custom_rbs_task_update",
                {"task_update_date": get_datetime().date(), "task_status": self.status},
            )

import frappe
from frappe.utils import get_datetime


def is_regency(doc):
    """Check custom_project_type field exists and is 'regency'"""
    if not hasattr(doc, "custom_project_type"):
        return False
    return (doc.custom_project_type or "").lower() == "regency"


def validate(doc, method):
    check_duplicate_subject(doc)
    check_custom_rbs_task_update_date(doc)
    validate_on_completed(doc)


def before_insert(doc, method):
    pass


def before_save(doc, method):
    set_default_rbs_task_row(doc)
    set_default_rbs_task_update_row(doc)
    handle_status_change_to_update_table(doc)


def check_duplicate_subject(doc):
    if not doc.subject:
        return

    exists = frappe.db.exists(
        "Task",
        {
            "subject": doc.subject,
            "name": ["!=", doc.name],  # ignore current doc
        },
    )

    if exists:
        frappe.throw(
            title="Duplicate",
            msg="Task already exists.",
        )


def check_custom_rbs_task_update_date(doc):
    if not is_regency(doc):
        return

    if doc.custom_rbs_task and len(doc.custom_rbs_task) > 0:
        if doc.custom_rbs_task_update:
            for row in doc.custom_rbs_task_update:
                if row.task_update_date < doc.custom_rbs_task[0].task_date:
                    frappe.throw("Task Update Date cannot be before Task Date")


def validate_on_completed(doc):
    """
    When task status = Completed:
    1. RBS Task row must have buyer_name, buyer_user_name, vibe_id
    2. All rows in RBS Task Update must have task_status = Completed
    """
    if not is_regency(doc):
        return

    if doc.status != "Completed":
        return

    # --- Check 1: RBS Task required fields ---
    if not doc.get("custom_rbs_task") or len(doc.custom_rbs_task) == 0:
        frappe.throw(
            "RBS Task table must have at least one record to mark task as <b>Completed</b>."
        )

    rbs_row = doc.custom_rbs_task[0]
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
            f"Cannot mark task as <b>Completed</b>.<br>"
            f"Please fill the following fields in RBS Task table:<br>"
            f"<ul>{missing_list}</ul>"
        )

    # --- Check 2: All update rows must be Completed + task_detail filled ---
    if doc.get("custom_rbs_task_update"):
        errors = []

        for i, row in enumerate(doc.custom_rbs_task_update):
            row_errors = []

            if row.task_status != "Completed":
                row_errors.append(
                    f"Status is <b>{row.task_status or 'Not Set'}</b> (must be Completed)"
                )

            if not row.get("task_detail"):
                row_errors.append("Task Detail is empty")

            if row_errors:
                errors.append(f"Row {i + 1}: " + " &amp; ".join(row_errors))

        if errors:
            frappe.throw(
                "Cannot mark task as <b>Completed</b>.<br>"
                "Please fix the following in RBS Task Update table:<br><br>"
                + "<br>".join(errors)
            )


def set_default_rbs_task_row(doc):
    if not is_regency(doc):
        return

    # Get today's date once
    today = get_datetime().date()

    if not doc.get("custom_rbs_task"):
        doc.append("custom_rbs_task", {"task_date": today})

    if not doc.get("custom_rbs_task_update") or len(doc.custom_rbs_task_update) == 0:
        doc.append(
            "custom_rbs_task_update",
            {"task_update_date": today, "task_status": "Received"},
        )

    # If exactly 1 row
    if len(doc.custom_rbs_task_update) == 1:
        row = doc.custom_rbs_task_update[0]

        if not row.task_update_date or not row.task_status:
            row.task_update_date = today
            row.task_status = "Received"


def set_default_rbs_task_update_row(doc):
    if not is_regency(doc):
        return

    if not doc.get("custom_rbs_task_update") or len(doc.custom_rbs_task_update) == 0:
        doc.append(
            "custom_rbs_task_update",
            {"task_update_date": get_datetime().date(), "task_status": "Received"},
        )


def handle_status_change_to_update_table(doc):
    """
    When status changes from Completed → RTS Info Needed / Revisions Needed,
    auto-add a new row in RBS Task Update with the new status.
    """
    if doc.is_new():
        return

    if not is_regency(doc):
        return

    # Statuses that trigger a new update row
    tracked_statuses = ["RTS Info Needed", "Revisions Needed"]

    if doc.status not in tracked_statuses:
        return

    # Get previous status from DB
    prev_status = frappe.db.get_value("Task", doc.name, "status")

    if prev_status != "Completed":
        return

    # Check if a row with this status already added (avoid duplicates on re-save)
    already_exists = any(
        row.task_status == doc.status for row in doc.custom_rbs_task_update
    )

    if not already_exists:
        doc.append(
            "custom_rbs_task_update",
            {"task_update_date": get_datetime().date(), "task_status": doc.status},
        )

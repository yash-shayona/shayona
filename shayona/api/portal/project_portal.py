import mimetypes
import os

import frappe
import frappe.utils

from frappe.core.api.file import get_max_file_size
from frappe.desk.doctype.notification_log.notification_log import (
    enqueue_create_notification,
)
from frappe.handler import ALLOWED_MIMETYPES
from frappe.utils import get_fullname, get_url_to_form
from shayona.api.employee_portal import (
    _start_employee_work_session,
    _stop_employee_work_session,
)
from shayona.permissions.project_portal import (
    PROJECT_PORTAL_ALLOWED_ROLES,
    PROJECT_PORTAL_BYPASS_ROLES,
    require_project_portal_access,
)

# These task states are not considered active for overdue filters in the portal.
PORTAL_CLOSED_TASK_STATUSES = ("Completed", "Cancelled")

# These fields are safe for a Task Owner to update from the employee portal.
PORTAL_TASK_OWNER_EDIT_FIELDS = frozenset(
    {"status", "progress", "description", "custom_task_owner"}
)

# These planning fields are available only to Project management roles in the portal.
PORTAL_TASK_MANAGER_EDIT_FIELDS = frozenset(
    {
        "subject",
        "priority",
        "type",
        "exp_start_date",
        "exp_end_date",
        "expected_time",
    }
)

# These portal roles can edit the Task planning fields in addition to owner updates.
PORTAL_TASK_MANAGER_ROLES = frozenset(
    {"System Manager", "Projects Manager", "Projects User"}
)

# These fixed ranges keep the portal report bounded while covering the employee timesheet view.
PORTAL_TIMESHEET_PERIODS = frozenset({"Today", "This Week", "This Month"})

# Task updates reuse the standard Frappe Comment timeline rather than a parallel DocType.
PORTAL_TASK_UPDATE_LIMIT = 30
PORTAL_TASK_UPDATE_MAX_LENGTH = 3000
PORTAL_TASK_UPDATE_OPTIONAL_FIELD_MAX_LENGTH = 1500

# Portal alerts use the standard Notification Log and are kept separate from unrelated app alerts.
PORTAL_NOTIFICATION_APP = "shayona"
PORTAL_NOTIFICATION_TYPE = "Alert"
PORTAL_NOTIFICATION_LIMIT = 30
PORTAL_PROJECT_MANAGER_ROLES = frozenset({"Projects Manager", "System Manager"})


def _get_portal_timesheet_date_range(period):
    # This returns server-derived dates so the browser cannot request an unbounded report range.
    today = frappe.utils.getdate(frappe.utils.today())

    if period == "Today":
        return today, today

    if period == "This Month":
        return frappe.utils.get_first_day(today), frappe.utils.get_last_day(today)

    return frappe.utils.add_days(today, -today.weekday()), today


def _get_portal_total_records(doctype, filters, or_filters=None):
    # This uses the same constrained filters as the page query so footer totals stay accurate.
    rows = frappe.db.get_list(
        doctype,
        filters=filters,
        or_filters=or_filters or {},
        fields=[{"COUNT": "name", "as": "total_records"}],
        limit_page_length=1,
    )

    return frappe.utils.cint(rows[0].total_records) if rows else 0


def _get_portal_task_fields(task_meta):
    # This returns only Task fields that exist in the current ERPNext schema.
    task_fields = ["name", "subject", "project", "status", "modified"]

    for fieldname in (
        "priority",
        "description",
        "type",
        "exp_start_date",
        "exp_end_date",
        "progress",
        "expected_time",
        "actual_time",
        "completed_on",
        "custom_task_owner",
    ):
        if task_meta.has_field(fieldname):
            task_fields.append(fieldname)

    return task_fields


def _get_task_select_options(task_meta, fieldname):
    # This reads the select choices from the installed Task schema instead of hard-coding them.
    field = task_meta.get_field(fieldname)
    options = frappe.utils.cstr(field.options if field else "")

    return [option for option in options.splitlines() if option]


def _get_portal_task_editable_fields(user, task_meta):
    # This returns the exact fields that the current portal role may change for an owned Task.
    editable_fields = set(PORTAL_TASK_OWNER_EDIT_FIELDS)
    user_roles = set(frappe.get_roles(user))

    if user == "Administrator" or user_roles & PORTAL_TASK_MANAGER_ROLES:
        editable_fields.update(PORTAL_TASK_MANAGER_EDIT_FIELDS)

    return sorted(
        fieldname for fieldname in editable_fields if task_meta.has_field(fieldname)
    )


def _has_project_portal_role(user):
    # This checks whether a reassigned Task Owner can open the Project Portal.
    if user == "Administrator":
        return True

    user_roles = set(frappe.get_roles(user))

    return bool(
        user_roles & (PROJECT_PORTAL_ALLOWED_ROLES | PROJECT_PORTAL_BYPASS_ROLES)
    )


def _get_portal_task_owner_options(current_owner=""):
    # This returns active Employees who can receive ownership of a portal Task.
    employee_rows = frappe.get_all(
        "Employee",
        filters={"status": "Active", "user_id": ["is", "set"]},
        fields=["user_id", "employee_name"],
        order_by="employee_name asc",
        limit_page_length=1000,
    )
    owner_options = []
    option_users = set()

    for employee in employee_rows:
        owner_user = employee.user_id

        if not owner_user or not _has_project_portal_role(owner_user):
            continue

        option_users.add(owner_user)
        owner_options.append(
            {
                "value": owner_user,
                "label": "{0} ({1})".format(
                    employee.employee_name or owner_user,
                    owner_user,
                ),
            }
        )

    # This preserves the current value for historical Tasks even if that user is no longer active.
    if current_owner and current_owner not in option_users:
        owner_options.insert(
            0,
            {"value": current_owner, "label": current_owner},
        )

    return owner_options


def _validate_portal_task_owner(task_owner):
    # This prevents reassignment to inactive users or users who cannot access this portal.
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": task_owner, "status": "Active"},
        ["name"],
        as_dict=True,
    )

    if not employee or not _has_project_portal_role(task_owner):
        frappe.throw(
            "Task Owner must be an active Employee with Project Portal access."
        )


def _get_portal_active_work_session(user):
    # This deliberately reads the employee's draft Timesheet instead of keeping
    # browser timer state, so task controls always reflect the authoritative row.
    employee_name = frappe.db.get_value(
        "Employee", {"user_id": user, "status": "Active"}, "name"
    )

    if not employee_name:
        return None

    timesheet_rows = frappe.db.get_all(
        "Timesheet",
        filters={
            "employee": employee_name,
            "start_date": frappe.utils.today(),
            "docstatus": 0,
        },
        fields=["name"],
        order_by="creation desc",
        limit_page_length=1,
    )

    if not timesheet_rows:
        return None

    timesheet = frappe.get_doc("Timesheet", timesheet_rows[0].name)

    for row in timesheet.time_logs:
        if not row.completed and row.from_time and not row.to_time:
            return {
                "timesheet": timesheet.name,
                "time_log": row.name,
                "project": row.project or "",
                "task": row.task or "",
                "from_time": row.from_time,
            }

    return None


def _get_owned_portal_task_for_work(user, task_name, task_meta):
    # Task ownership is checked before loading the document and again by the
    # write endpoint before save, matching the existing portal task update flow.
    if not task_meta.has_field("custom_task_owner"):
        frappe.throw("Task field custom_task_owner is required for My Tasks.")

    task_rows = frappe.db.get_list(
        "Task",
        filters={"name": task_name, "custom_task_owner": user, "is_group": 0},
        fields=["name"],
        limit_page_length=1,
    )

    if not task_rows:
        frappe.throw("Task does not exist or you do not have permission.")

    task_doc = frappe.get_doc("Task", task_name)

    if task_doc.custom_task_owner != user:
        frappe.throw("Task Owner changed. Refresh the task before continuing.")

    return task_doc


def _get_portal_task_updates(task_name):
    # This returns only human comments; attachment/system comments remain in Desk.
    comment_rows = frappe.db.get_all(
        "Comment",
        filters={
            "reference_doctype": "Task",
            "reference_name": task_name,
            "comment_type": "Comment",
        },
        fields=["name", "content", "comment_by", "owner", "creation"],
        order_by="creation desc",
        limit_page_length=PORTAL_TASK_UPDATE_LIMIT,
    )

    return [
        {
            "name": row.name,
            # Portal text is rendered as text, not Desk rich HTML.
            "content": frappe.utils.strip_html(row.content or "").strip(),
            "author": row.comment_by or row.owner or "Employee",
            "created_at": row.creation,
        }
        for row in comment_rows
    ]


def _get_portal_task_attachments(task_name):
    # Files are private and attached to the same Task, so standard File access applies.
    attachment_rows = frappe.db.get_all(
        "File",
        filters={"attached_to_doctype": "Task", "attached_to_name": task_name},
        fields=["name", "file_name", "file_url", "creation"],
        order_by="creation desc",
        limit_page_length=PORTAL_TASK_UPDATE_LIMIT,
    )

    return [
        {
            "name": row.name,
            "file_name": row.file_name or row.name,
            "file_url": row.file_url or "",
            "created_at": row.creation,
        }
        for row in attachment_rows
    ]


def _clean_portal_task_update_text(value, field_label, max_length, required=False):
    # Updates are stored as plain text so untrusted markup never becomes portal HTML.
    text = frappe.utils.strip_html(frappe.utils.cstr(value or "")).strip()

    if required and not text:
        frappe.throw("{0} is required.".format(field_label))

    if len(text) > max_length:
        frappe.throw(
            "{0} cannot exceed {1} characters.".format(field_label, max_length)
        )

    return text


def _get_portal_project_manager_recipients(project_name, exclude_user=""):
    # Project User is the only standard Project-level user assignment. Restricting
    # recipients to its manager-role members avoids alerting every global manager.
    if not project_name:
        return []

    project = frappe.db.get_value(
        "Project", project_name, ["name", "owner"], as_dict=True
    )

    if not project:
        return []

    project_user_rows = frappe.get_all(
        "Project User",
        filters={"parent": project_name, "parenttype": "Project"},
        fields=["user"],
    )
    project_users = {
        row.user for row in project_user_rows if frappe.utils.cstr(row.user).strip()
    }
    manager_users = set()

    if project_users:
        manager_users = set(
            frappe.get_all(
                "Has Role",
                filters={
                    "parent": ["in", sorted(project_users)],
                    "role": ["in", sorted(PORTAL_PROJECT_MANAGER_ROLES)],
                },
                pluck="parent",
            )
        )

    # Older Projects may not have a manager-role user in their website Users table.
    # The Project creator is the narrowest native fallback, rather than all managers.
    recipient_users = manager_users or {project.owner}
    recipient_users.discard(exclude_user)

    if not recipient_users:
        return []

    user_rows = frappe.get_all(
        "User",
        filters={"name": ["in", sorted(recipient_users)], "enabled": 1},
        fields=["name", "email"],
    )

    return [
        row.email
        for row in user_rows
        if row.email and row.name != exclude_user and row.email != exclude_user
    ]


def _enqueue_portal_task_notification(
    recipients,
    task,
    title,
    description,
    from_user="Administrator",
    dedupe_on=None,
):
    # Notification Log handles recipient preferences, realtime delivery, and audit history.
    if not recipients:
        return

    enqueue_create_notification(
        recipients,
        {
            "type": PORTAL_NOTIFICATION_TYPE,
            "title": title,
            "description": description,
            "document_type": "Task",
            "document_name": task.name,
            "link": get_url_to_form("Task", task.name),
            "app": PORTAL_NOTIFICATION_APP,
            "from_user": from_user,
        },
        dedupe_on=dedupe_on,
    )


def _notify_portal_project_managers_about_blocker(task, blocker, reported_by):
    # A blocker is visible to only the assigned Project managers, with project owner fallback.
    recipients = _get_portal_project_manager_recipients(
        task.project, exclude_user=reported_by
    )

    _enqueue_portal_task_notification(
        recipients,
        task,
        "Blocker reported · {0}".format(task.name),
        "{0} reported a blocker on {1}: {2}".format(
            get_fullname(reported_by), task.subject or task.name, blocker
        ),
        from_user=reported_by,
    )


def send_employee_project_portal_due_task_reminders():
    # The daily scheduler is idempotent: each Task/category/day shares one Notification Log.
    task_meta = frappe.get_meta("Task")

    if not (
        task_meta.has_field("custom_task_owner")
        and task_meta.has_field("exp_end_date")
    ):
        return

    today = frappe.utils.getdate(frappe.utils.today())
    tomorrow = frappe.utils.add_days(today, 1)
    reminder_end = frappe.utils.get_datetime("{0} 23:59:59".format(tomorrow))
    task_rows = frappe.get_all(
        "Task",
        filters={
            "is_group": 0,
            "custom_task_owner": ["is", "set"],
            "status": ["not in", PORTAL_CLOSED_TASK_STATUSES],
            "exp_end_date": ["<=", reminder_end],
        },
        fields=["name", "subject", "exp_end_date", "custom_task_owner"],
    )

    for task in task_rows:
        due_date = frappe.utils.getdate(task.exp_end_date)

        if due_date < today:
            reminder_label = "Overdue task"
            due_message = "is overdue"
        elif due_date == today:
            reminder_label = "Due today"
            due_message = "is due today"
        elif due_date == tomorrow:
            reminder_label = "Due tomorrow"
            due_message = "is due tomorrow"
        else:
            continue

        reminder_date = frappe.utils.formatdate(today)
        _enqueue_portal_task_notification(
            [task.custom_task_owner],
            task,
            "{0} · {1}".format(reminder_label, reminder_date),
            "{0} ({1}) {2}. Due date: {3}.".format(
                task.subject or task.name,
                task.name,
                due_message,
                frappe.utils.formatdate(due_date),
            ),
            dedupe_on=["title", "document_name", "app"],
        )


def _get_project_portal_notifications(user):
    # The app filter prevents the portal panel from exposing a user's unrelated Desk alerts.
    notification_rows = frappe.db.get_all(
        "Notification Log",
        filters={"for_user": user, "app": PORTAL_NOTIFICATION_APP},
        fields=[
            "name",
            "title",
            "subject",
            "description",
            "document_type",
            "document_name",
            "link",
            "read",
            "creation",
        ],
        order_by="creation desc",
        limit_page_length=PORTAL_NOTIFICATION_LIMIT,
    )

    return {
        "notifications": [
            {
                "name": row.name,
                "title": row.title or row.subject or "Project Portal update",
                "description": frappe.utils.strip_html(row.description or "").strip(),
                "document_type": row.document_type or "",
                "document_name": row.document_name or "",
                "link": row.link or "",
                "read": frappe.utils.cint(row.read),
                "created_at": row.creation,
            }
            for row in notification_rows
        ],
        "unread_count": frappe.db.count(
            "Notification Log",
            filters={"for_user": user, "app": PORTAL_NOTIFICATION_APP, "read": 0},
        ),
    }


def _get_my_task_detail_payload(task_row, task_meta, user):
    # This creates the read and edit data for one Task that is owned by the logged-in user.
    project_name = task_row.project or ""
    project_label = project_name

    if project_name:
        project_rows = frappe.db.get_list(
            "Project",
            filters={"name": project_name},
            fields=["name", "project_name"],
            limit_page_length=1,
        )

        if project_rows:
            project_label = project_rows[0].project_name or project_name

    status_options = [
        status
        for status in _get_task_select_options(task_meta, "status")
        if status != "Template"
    ]
    editable_fields = _get_portal_task_editable_fields(user, task_meta)
    task_type_options = []

    if "type" in editable_fields:
        task_type_options = frappe.db.get_list(
            "Task Type",
            fields=["name"],
            order_by="name asc",
            limit_page_length=200,
        )

    return {
        "name": task_row.name,
        "subject": task_row.subject or task_row.name,
        "project": project_name,
        "project_label": project_label,
        "status": task_row.status or "Open",
        "priority": task_row.get("priority") or "",
        "activity_type": task_row.get("type") or "",
        # Notes are rendered as plain text in the portal, so rich HTML is never injected.
        "description": frappe.utils.strip_html(task_row.get("description") or ""),
        "start_date": task_row.get("exp_start_date"),
        "due_date": task_row.get("exp_end_date"),
        "progress": task_row.get("progress") or 0,
        "expected_time": task_row.get("expected_time") or 0,
        "actual_time": task_row.get("actual_time") or 0,
        "task_owner": task_row.get("custom_task_owner") or "",
        "active_work": _get_portal_active_work_session(user),
        "updates": _get_portal_task_updates(task_row.name),
        "attachments": _get_portal_task_attachments(task_row.name),
        "editable_fields": editable_fields,
        "edit_options": {
            "statuses": status_options,
            "priorities": _get_task_select_options(task_meta, "priority"),
            "task_types": [task_type.name for task_type in task_type_options],
            "task_owners": _get_portal_task_owner_options(
                task_row.get("custom_task_owner") or ""
            ),
        },
    }


@frappe.whitelist()
def employee_project_portal_get_dashboard():
    # API Method:
    # employee_project_portal_get_dashboard

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    # This blocks direct API calls from users outside the Project Portal roles.
    require_project_portal_access(user)

    # ---------------------------------------------------------
    # Logged-in Employee
    # ---------------------------------------------------------

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "company", "department"],
        as_dict=True,
    )

    # ---------------------------------------------------------
    # Default Response
    # ---------------------------------------------------------

    dashboard_data = {
        "setup_complete": False,
        "missing_setup": [],
        "user": {
            "email": user,
            "employee": "",
            "employee_name": frappe.utils.get_fullname(user),
            "company": "",
            "department": "",
        },
        "summary": {
            "active_projects": 0,
            "my_tasks": 0,
            "overdue_tasks": 0,
            "completed_this_week": 0,
        },
        "current_work": None,
        "upcoming_deadlines": [],
        "recent_activity": [],
        "project_progress": [],
    }

    # ---------------------------------------------------------
    # Employee Setup Validation
    # ---------------------------------------------------------

    if not employee:
        dashboard_data["missing_setup"] = [
            "Active Employee is not linked with logged-in User"
        ]

    else:
        dashboard_data["setup_complete"] = True

        dashboard_data["user"] = {
            "email": user,
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "company": employee.company,
            "department": employee.department,
        }

        # -----------------------------------------------------
        # Meta
        # -----------------------------------------------------

        project_meta = frappe.get_meta("Project")
        task_meta = frappe.get_meta("Task")

        # -----------------------------------------------------
        # Today and Current Week
        # -----------------------------------------------------

        today = frappe.utils.today()

        today_date = frappe.utils.getdate(today)

        week_start = frappe.utils.add_days(today, -today_date.weekday())

        day_end = today + " 23:59:59"
        week_start_datetime = week_start + " 00:00:00"

        upcoming_end_date = frappe.utils.add_days(today, 30)

        # -----------------------------------------------------
        # Project Fields
        # -----------------------------------------------------

        project_fields = ["name", "project_name", "status", "modified"]

        if project_meta.has_field("percent_complete"):
            project_fields.append("percent_complete")

        if project_meta.has_field("expected_start_date"):
            project_fields.append("expected_start_date")

        if project_meta.has_field("expected_end_date"):
            project_fields.append("expected_end_date")

        # -----------------------------------------------------
        # Task Fields
        # -----------------------------------------------------

        task_fields = [
            "name",
            "subject",
            "project",
            "status",
            "modified",
            "modified_by",
        ]

        if task_meta.has_field("priority"):
            task_fields.append("priority")

        if task_meta.has_field("exp_start_date"):
            task_fields.append("exp_start_date")

        if task_meta.has_field("exp_end_date"):
            task_fields.append("exp_end_date")

        if task_meta.has_field("completed_on"):
            task_fields.append("completed_on")

        # -----------------------------------------------------
        # Permission-wise Active Projects
        # -----------------------------------------------------

        active_project_rows = frappe.db.get_list(
            "Project",
            filters={"status": "Open"},
            fields=project_fields,
            order_by="modified desc",
            limit_page_length=1000,
        )

        dashboard_data["summary"]["active_projects"] = len(active_project_rows)

        # -----------------------------------------------------
        # My Open Tasks
        #
        # Current EWP Task creation stores logged-in user in:
        # custom_task_owner
        # -----------------------------------------------------

        my_task_filters = {
            "custom_task_owner": user,
            "status": ["not in", ["Completed", "Cancelled"]],
            "is_group": 0,
        }

        my_task_rows = frappe.db.get_list(
            "Task",
            filters=my_task_filters,
            fields=task_fields,
            order_by="modified desc",
            limit_page_length=1000,
        )

        dashboard_data["summary"]["my_tasks"] = len(my_task_rows)

        # -----------------------------------------------------
        # Overdue Tasks
        # -----------------------------------------------------

        overdue_rows = []

        if task_meta.has_field("exp_end_date"):
            overdue_rows = frappe.db.get_list(
                "Task",
                filters={
                    "custom_task_owner": user,
                    "status": ["not in", ["Completed", "Cancelled"]],
                    "is_group": 0,
                    "exp_end_date": ["<", today],
                },
                fields=["name"],
                limit_page_length=1000,
            )

        dashboard_data["summary"]["overdue_tasks"] = len(overdue_rows)

        # -----------------------------------------------------
        # Completed This Week
        # -----------------------------------------------------

        completed_week_rows = []

        if task_meta.has_field("completed_on"):
            completed_week_rows = frappe.db.get_list(
                "Task",
                filters={
                    "custom_task_owner": user,
                    "status": "Completed",
                    "is_group": 0,
                    "completed_on": ["between", [week_start_datetime, day_end]],
                },
                fields=["name"],
                limit_page_length=1000,
            )

        else:
            # Fallback only when completed_on field is unavailable.
            completed_week_rows = frappe.db.get_list(
                "Task",
                filters={
                    "custom_task_owner": user,
                    "status": "Completed",
                    "is_group": 0,
                    "modified": ["between", [week_start_datetime, day_end]],
                },
                fields=["name"],
                limit_page_length=1000,
            )

        dashboard_data["summary"]["completed_this_week"] = len(completed_week_rows)

        # -----------------------------------------------------
        # Project Label Map
        # -----------------------------------------------------

        project_label_map = {}

        for project_row in active_project_rows:
            project_label_map[project_row.name] = (
                project_row.project_name or project_row.name
            )

        # -----------------------------------------------------
        # Current Running Work Session
        # -----------------------------------------------------

        timesheet_rows = frappe.db.get_all(
            "Timesheet",
            filters={"employee": employee.name, "start_date": today, "docstatus": 0},
            fields=["name"],
            order_by="creation desc",
            limit_page_length=1,
        )

        if timesheet_rows:
            timesheet = frappe.get_doc("Timesheet", timesheet_rows[0].name)

            current_row = None

            for row in timesheet.time_logs:
                if not row.completed and row.from_time and not row.to_time:
                    current_row = row
                    break

            if current_row:
                task_label = ""
                project_label = ""

                if current_row.task:
                    task_label = (
                        frappe.db.get_value("Task", current_row.task, "subject")
                        or current_row.task
                    )

                if current_row.project:
                    project_label = (
                        frappe.db.get_value(
                            "Project", current_row.project, "project_name"
                        )
                        or current_row.project
                    )

                dashboard_data["current_work"] = {
                    "timesheet": timesheet.name,
                    "time_log": current_row.name,
                    "project": (current_row.project or ""),
                    "project_label": (project_label or ""),
                    "task": (current_row.task or ""),
                    "task_label": (task_label or ""),
                    "activity_type": (current_row.activity_type or ""),
                    "description": (current_row.description or ""),
                    "from_time": current_row.from_time,
                }

        # -----------------------------------------------------
        # Upcoming Deadlines
        # Next 30 days
        # -----------------------------------------------------

        upcoming_rows = []

        if task_meta.has_field("exp_end_date"):
            upcoming_rows = frappe.db.get_list(
                "Task",
                filters={
                    "custom_task_owner": user,
                    "status": ["not in", ["Completed", "Cancelled"]],
                    "is_group": 0,
                    "exp_end_date": ["between", [today, upcoming_end_date]],
                },
                fields=task_fields,
                order_by="exp_end_date asc",
                limit_page_length=6,
            )

        upcoming_deadlines = []

        for task_row in upcoming_rows:
            project_label = (
                project_label_map.get(task_row.project) or task_row.project or ""
            )

            upcoming_deadlines.append(
                {
                    "task": task_row.name,
                    "subject": (task_row.subject or task_row.name),
                    "project": (task_row.project or ""),
                    "project_label": project_label,
                    "status": (task_row.status or ""),
                    "priority": (task_row.get("priority") or ""),
                    "due_date": (task_row.get("exp_end_date")),
                }
            )

        dashboard_data["upcoming_deadlines"] = upcoming_deadlines

        # -----------------------------------------------------
        # Recent Activity
        #
        # First MVP:
        # Recently modified Tasks are shown.
        #
        # Later phase:
        # Comment / Version / assignment activity timeline.
        # -----------------------------------------------------

        recent_task_rows = frappe.db.get_list(
            "Task",
            filters={"custom_task_owner": user, "is_group": 0},
            fields=task_fields,
            order_by="modified desc",
            limit_page_length=6,
        )

        recent_activity = []

        for task_row in recent_task_rows:
            project_label = (
                project_label_map.get(task_row.project) or task_row.project or ""
            )

            recent_activity.append(
                {
                    "reference_doctype": "Task",
                    "reference_name": task_row.name,
                    "activity_type": "Task Updated",
                    "title": (task_row.subject or task_row.name),
                    "project": (task_row.project or ""),
                    "project_label": project_label,
                    "status": (task_row.status or ""),
                    "modified": task_row.modified,
                    "modified_by": (task_row.modified_by or ""),
                }
            )

        dashboard_data["recent_activity"] = recent_activity

        # -----------------------------------------------------
        # Project Progress
        # Latest six accessible active Projects
        # -----------------------------------------------------

        project_progress = []

        progress_project_rows = active_project_rows[:6]

        for project_row in progress_project_rows:
            percent_complete = 0

            if project_meta.has_field("percent_complete"):
                percent_complete = project_row.get("percent_complete") or 0

            project_progress.append(
                {
                    "project": project_row.name,
                    "project_name": (project_row.project_name or project_row.name),
                    "status": (project_row.status or ""),
                    "percent_complete": (percent_complete),
                    "expected_start_date": (project_row.get("expected_start_date")),
                    "expected_end_date": (project_row.get("expected_end_date")),
                }
            )

        dashboard_data["project_progress"] = project_progress

    frappe.response["message"] = dashboard_data


@frappe.whitelist()
def employee_project_portal_get_projects():
    # API Method:
    # employee_project_portal_get_projects

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    # This blocks direct API calls from users outside the Project Portal roles.
    require_project_portal_access(user)

    # ---------------------------------------------------------
    # Logged-in Employee
    # ---------------------------------------------------------

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "company", "department"],
        as_dict=True,
    )

    # ---------------------------------------------------------
    # Request Parameters
    # ---------------------------------------------------------

    search = frappe.utils.cstr(frappe.form_dict.get("search") or "").strip()

    status = frappe.utils.cstr(frappe.form_dict.get("status") or "Open").strip()

    customer = frappe.utils.cstr(frappe.form_dict.get("customer") or "").strip()

    sort_key = frappe.utils.cstr(frappe.form_dict.get("sort") or "recent").strip()

    page = frappe.utils.cint(frappe.form_dict.get("page") or 1)

    page_length = frappe.utils.cint(frappe.form_dict.get("page_length") or 10)

    # ---------------------------------------------------------
    # Pagination Guards
    # ---------------------------------------------------------

    if page < 1:
        page = 1

    if page_length < 1:
        page_length = 10

    if page_length > 50:
        page_length = 50

    limit_start = (page - 1) * page_length

    # ---------------------------------------------------------
    # Default Response
    # ---------------------------------------------------------

    response_data = {
        "setup_complete": False,
        "missing_setup": [],
        "user": {
            "email": user,
            "employee": "",
            "employee_name": frappe.utils.get_fullname(user),
            "company": "",
            "department": "",
        },
        "filters": {
            "search": search,
            "status": status,
            "customer": customer,
            "sort": sort_key,
        },
        "pagination": {
            "page": page,
            "page_length": page_length,
            "has_previous": page > 1,
            "has_more": False,
            "total_records": 0,
            "total_pages": 0,
        },
        "projects": [],
    }

    # ---------------------------------------------------------
    # Employee Setup Validation
    # ---------------------------------------------------------

    if not employee:
        response_data["missing_setup"] = [
            "Active Employee is not linked with logged-in User"
        ]

    else:
        response_data["setup_complete"] = True

        response_data["user"] = {
            "email": user,
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "company": employee.company,
            "department": employee.department,
        }

        # -----------------------------------------------------
        # Project and Task Meta
        # -----------------------------------------------------

        project_meta = frappe.get_meta("Project")
        task_meta = frappe.get_meta("Task")

        # -----------------------------------------------------
        # Project Fields
        # -----------------------------------------------------

        project_fields = ["name", "project_name", "status", "modified", "modified_by"]

        if project_meta.has_field("customer"):
            project_fields.append("customer")

        if project_meta.has_field("project_type"):
            project_fields.append("project_type")

        if project_meta.has_field("percent_complete"):
            project_fields.append("percent_complete")

        if project_meta.has_field("expected_start_date"):
            project_fields.append("expected_start_date")

        if project_meta.has_field("expected_end_date"):
            project_fields.append("expected_end_date")

        # -----------------------------------------------------
        # Project Filters
        # -----------------------------------------------------

        project_filters = {}

        if status and status != "All":
            project_filters["status"] = status

        if customer and project_meta.has_field("customer"):
            project_filters["customer"] = customer

        # -----------------------------------------------------
        # Search Filters
        # -----------------------------------------------------

        project_or_filters = {}

        if search:
            search_value = "%{0}%".format(search)

            project_or_filters["name"] = ["like", search_value]

            project_or_filters["project_name"] = ["like", search_value]

            if project_meta.has_field("customer"):
                project_or_filters["customer"] = ["like", search_value]

        # -----------------------------------------------------
        # Controlled Sorting
        #
        # Never accept a raw order_by value from browser.
        # -----------------------------------------------------

        order_by = "modified desc"

        if sort_key == "name":
            order_by = "project_name asc"

        elif sort_key == "progress" and project_meta.has_field("percent_complete"):
            order_by = "percent_complete desc"

        elif sort_key == "due_date" and project_meta.has_field("expected_end_date"):
            order_by = "expected_end_date asc, " "project_name asc"

        # -----------------------------------------------------
        # Permission-wise Projects
        #
        # Fetch one extra row to determine has_more.
        # -----------------------------------------------------

        total_records = _get_portal_total_records(
            "Project", project_filters, project_or_filters
        )
        total_pages = (total_records + page_length - 1) // page_length

        page = min(page, total_pages or 1)

        limit_start = (page - 1) * page_length
        response_data["pagination"].update(
            {
                "page": page,
                "has_previous": page > 1,
                "total_records": total_records,
                "total_pages": total_pages,
            }
        )

        project_rows = frappe.db.get_list(
            "Project",
            filters=project_filters,
            or_filters=project_or_filters,
            fields=project_fields,
            order_by=order_by,
            limit_start=limit_start,
            limit_page_length=page_length + 1,
        )

        # -----------------------------------------------------
        # Pagination State
        # -----------------------------------------------------

        has_more = len(project_rows) > page_length

        if has_more:
            project_rows = project_rows[:page_length]

        response_data["pagination"]["has_more"] = has_more

        # -----------------------------------------------------
        # Project Names
        # -----------------------------------------------------

        project_names = []

        for project_row in project_rows:
            project_names.append(project_row.name)

        # -----------------------------------------------------
        # Permission-wise Tasks for Returned Projects
        #
        # These counts contain only Tasks that the logged-in
        # user is permitted to read.
        # -----------------------------------------------------

        task_summary_map = {}

        for project_name in project_names:
            task_summary_map[project_name] = {
                "total": 0,
                "open": 0,
                "completed": 0,
                "overdue": 0,
            }

        task_rows = []

        if project_names:
            task_fields = ["name", "project", "status"]

            if task_meta.has_field("exp_end_date"):
                task_fields.append("exp_end_date")

            task_filters = {"project": ["in", project_names], "is_group": 0}

            task_rows = frappe.db.get_list(
                "Task",
                filters=task_filters,
                fields=task_fields,
                order_by="project asc",
                limit_page_length=5000,
            )

        # -----------------------------------------------------
        # Build Task Summary
        # -----------------------------------------------------

        today = frappe.utils.getdate(frappe.utils.today())

        for task_row in task_rows:
            project_name = task_row.project

            if not project_name or project_name not in task_summary_map:
                continue

            task_status = task_row.status or ""

            # Cancelled Tasks are not included in progress count.
            if task_status == "Cancelled":
                continue

            task_summary = task_summary_map[project_name]

            task_summary["total"] = task_summary["total"] + 1

            if task_status == "Completed":
                task_summary["completed"] = task_summary["completed"] + 1

            else:
                task_summary["open"] = task_summary["open"] + 1

                if task_meta.has_field("exp_end_date") and task_row.get("exp_end_date"):
                    task_due_date = frappe.utils.getdate(task_row.get("exp_end_date"))

                    if task_due_date < today:
                        task_summary["overdue"] = task_summary["overdue"] + 1

        # -----------------------------------------------------
        # Final Project Response
        # -----------------------------------------------------

        projects = []

        for project_row in project_rows:
            percent_complete = 0

            if project_meta.has_field("percent_complete"):
                percent_complete = project_row.get("percent_complete") or 0

            if percent_complete < 0:
                percent_complete = 0

            if percent_complete > 100:
                percent_complete = 100

            expected_end_date = None
            is_overdue = False

            if project_meta.has_field("expected_end_date"):
                expected_end_date = project_row.get("expected_end_date")

                if expected_end_date and project_row.status not in [
                    "Completed",
                    "Cancelled",
                ]:
                    project_due_date = frappe.utils.getdate(expected_end_date)

                    if project_due_date < today:
                        is_overdue = True

            projects.append(
                {
                    "name": project_row.name,
                    "project_name": (project_row.project_name or project_row.name),
                    "status": (project_row.status or ""),
                    "customer": (project_row.get("customer") or ""),
                    "project_type": (project_row.get("project_type") or ""),
                    "percent_complete": (percent_complete),
                    "expected_start_date": (project_row.get("expected_start_date")),
                    "expected_end_date": (expected_end_date),
                    "is_overdue": is_overdue,
                    "task_summary": (
                        task_summary_map.get(project_row.name)
                        or {"total": 0, "open": 0, "completed": 0, "overdue": 0}
                    ),
                    "modified": project_row.modified,
                    "modified_by": (project_row.modified_by or ""),
                }
            )

        response_data["projects"] = projects

    frappe.response["message"] = response_data


@frappe.whitelist()
def employee_project_portal_get_project_workspace():
    # API Method:
    # employee_project_portal_get_project_workspace
    # This returns only read-only Project and Task data for the portal workspace.

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    # This blocks direct API calls from users outside the Project Portal roles.
    require_project_portal_access(user)

    project_name = frappe.utils.cstr(frappe.form_dict.get("project") or "").strip()

    if not project_name:
        frappe.throw("Please select a Project.")

    search = frappe.utils.cstr(frappe.form_dict.get("search") or "").strip()

    status = frappe.utils.cstr(frappe.form_dict.get("status") or "All").strip()

    page = frappe.utils.cint(frappe.form_dict.get("page") or 1)

    page_length = frappe.utils.cint(frappe.form_dict.get("page_length") or 10)

    # These guards keep the browser from requesting invalid or excessive pages.
    if page < 1:
        page = 1

    if page_length < 1:
        page_length = 10

    if page_length > 50:
        page_length = 50

    project_meta = frappe.get_meta("Project")
    task_meta = frappe.get_meta("Task")

    # These are standard Project fields. Optional fields are added only when present.
    project_fields = ["name", "project_name", "status", "modified"]

    for fieldname in (
        "customer",
        "project_type",
        "priority",
        "percent_complete",
        "expected_start_date",
        "expected_end_date",
        "notes",
    ):
        if project_meta.has_field(fieldname):
            project_fields.append(fieldname)

    # get_list applies the existing Project permission rules before any detail is returned.
    project_rows = frappe.db.get_list(
        "Project",
        filters={"name": project_name},
        fields=project_fields,
        limit_page_length=1,
    )

    if not project_rows:
        frappe.throw("Project does not exist or you do not have permission.")

    project_row = project_rows[0]

    # The member table belongs to this already-permitted Project record.
    project_doc = frappe.get_doc("Project", project_name)
    members = []

    for member in project_doc.get("users") or []:
        members.append(
            {
                "user": member.user or "",
                "full_name": member.full_name or member.user or "",
                "image": member.image or "",
            }
        )

    # The workspace only shows leaf Tasks. Parent groups are structural, not work items.
    task_filters = {"project": project_name, "is_group": 0}

    if status and status != "All":
        task_filters["status"] = status

    task_or_filters = {}

    if search:
        search_value = "%{0}%".format(search)
        task_or_filters = {
            "name": ["like", search_value],
            "subject": ["like", search_value],
        }

    total_records = _get_portal_total_records(
        "Task", task_filters, task_or_filters
    )
    total_pages = (total_records + page_length - 1) // page_length

    page = min(page, total_pages or 1)

    # These fields are used by the read-only task table and are checked for compatibility.
    task_fields = ["name", "subject", "status", "modified"]

    for fieldname in (
        "priority",
        "exp_end_date",
        "progress",
        "expected_time",
        "actual_time",
        "custom_task_owner",
    ):
        if task_meta.has_field(fieldname):
            task_fields.append(fieldname)

    task_rows = frappe.db.get_list(
        "Task",
        filters=task_filters,
        or_filters=task_or_filters,
        fields=task_fields,
        order_by="exp_end_date asc, modified desc",
        limit_start=(page - 1) * page_length,
        limit_page_length=page_length + 1,
    )

    has_more = len(task_rows) > page_length

    if has_more:
        task_rows = task_rows[:page_length]

    # This grouped query gives an accurate visible-task summary without loading every Task row.
    summary_rows = frappe.db.get_list(
        "Task",
        filters={"project": project_name, "is_group": 0},
        fields=["status", {"COUNT": "name", "as": "task_count"}],
        group_by="status",
        limit_page_length=20,
    )

    task_summary = {
        "total": 0,
        "open": 0,
        "working": 0,
        "review": 0,
        "completed": 0,
    }

    for summary_row in summary_rows:
        task_count = frappe.utils.cint(summary_row.task_count)
        task_status = summary_row.status or ""

        if task_status == "Cancelled":
            continue

        task_summary["total"] += task_count

        if task_status == "Completed":
            task_summary["completed"] += task_count
        elif task_status == "Working":
            task_summary["working"] += task_count
        elif task_status == "Pending Review":
            task_summary["review"] += task_count
        else:
            task_summary["open"] += task_count

    response_data = {
        "project": {
            "name": project_row.name,
            "project_name": project_row.project_name or project_row.name,
            "status": project_row.status or "",
            "customer": project_row.get("customer") or "",
            "project_type": project_row.get("project_type") or "",
            "priority": project_row.get("priority") or "",
            "percent_complete": project_row.get("percent_complete") or 0,
            "expected_start_date": project_row.get("expected_start_date"),
            "expected_end_date": project_row.get("expected_end_date"),
            # Notes are converted to plain text so portal rendering never injects rich HTML.
            "notes": frappe.utils.strip_html(project_row.get("notes") or ""),
            "members": members,
        },
        "filters": {
            "search": search,
            "status": status,
        },
        "task_summary": task_summary,
        "tasks": task_rows,
        "pagination": {
            "page": page,
            "page_length": page_length,
            "has_previous": page > 1,
            "has_more": has_more,
            "total_records": total_records,
            "total_pages": total_pages,
        },
    }

    frappe.response["message"] = response_data


@frappe.whitelist()
def employee_project_portal_get_my_tasks():
    # This returns the current user's permitted, non-group Tasks with server-side filters.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_meta = frappe.get_meta("Task")

    if not task_meta.has_field("custom_task_owner"):
        frappe.throw("Task field custom_task_owner is required for My Tasks.")

    search = frappe.utils.cstr(frappe.form_dict.get("search") or "").strip()
    status = frappe.utils.cstr(frappe.form_dict.get("status") or "All").strip()
    priority = frappe.utils.cstr(frappe.form_dict.get("priority") or "All").strip()
    due = frappe.utils.cstr(frappe.form_dict.get("due") or "All").strip()
    page = max(frappe.utils.cint(frappe.form_dict.get("page") or 1), 1)
    page_length = frappe.utils.cint(frappe.form_dict.get("page_length") or 10)
    page_length = min(max(page_length, 1), 50)

    # This base filter limits My Tasks to the owner field used by the existing EWP flow.
    task_filters = {
        "custom_task_owner": user,
        "is_group": 0,
    }

    if status and status != "All":
        task_filters["status"] = status

    if priority and priority != "All" and task_meta.has_field("priority"):
        task_filters["priority"] = priority

    today = frappe.utils.today()

    if due == "Overdue" and task_meta.has_field("exp_end_date"):
        task_filters["exp_end_date"] = ["<", today]
        task_filters["status"] = ["not in", PORTAL_CLOSED_TASK_STATUSES]
    elif due == "Today" and task_meta.has_field("exp_end_date"):
        task_filters["exp_end_date"] = [
            "between",
            ["{0} 00:00:00".format(today), "{0} 23:59:59".format(today)],
        ]

    task_or_filters = {}

    if search:
        search_value = "%{0}%".format(search)
        task_or_filters = {
            "name": ["like", search_value],
            "subject": ["like", search_value],
        }

    total_records = _get_portal_total_records(
        "Task", task_filters, task_or_filters
    )
    total_pages = (total_records + page_length - 1) // page_length

    page = min(page, total_pages or 1)

    task_rows = frappe.db.get_list(
        "Task",
        filters=task_filters,
        or_filters=task_or_filters,
        fields=_get_portal_task_fields(task_meta),
        order_by="exp_end_date asc, modified desc",
        limit_start=(page - 1) * page_length,
        limit_page_length=page_length + 1,
    )

    has_more = len(task_rows) > page_length

    if has_more:
        task_rows = task_rows[:page_length]

    today_date = frappe.utils.getdate(today)
    tasks = []

    for task_row in task_rows:
        due_date = task_row.get("exp_end_date")
        is_overdue = False

        if due_date and task_row.status not in PORTAL_CLOSED_TASK_STATUSES:
            is_overdue = frappe.utils.getdate(due_date) < today_date

        tasks.append(
            {
                "name": task_row.name,
                "subject": task_row.subject or task_row.name,
                "project": task_row.project or "",
                "status": task_row.status or "Open",
                "priority": task_row.get("priority") or "",
                "due_date": due_date,
                "progress": task_row.get("progress") or 0,
                "expected_time": task_row.get("expected_time") or 0,
                "actual_time": task_row.get("actual_time") or 0,
                "is_overdue": is_overdue,
            }
        )

    frappe.response["message"] = {
        "filters": {
            "search": search,
            "status": status,
            "priority": priority,
            "due": due,
        },
        "tasks": tasks,
        "pagination": {
            "page": page,
            "page_length": page_length,
            "has_previous": page > 1,
            "has_more": has_more,
            "total_records": total_records,
            "total_pages": total_pages,
        },
    }


@frappe.whitelist()
def employee_project_portal_get_my_timesheets():
    # This returns only the logged-in employee's standard Timesheets and time-log summaries.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    period = frappe.utils.cstr(frappe.form_dict.get("period") or "This Week").strip()
    status = frappe.utils.cstr(frappe.form_dict.get("status") or "All").strip()
    page = max(frappe.utils.cint(frappe.form_dict.get("page") or 1), 1)
    page_length = min(
        max(frappe.utils.cint(frappe.form_dict.get("page_length") or 10), 1),
        50,
    )

    if period not in PORTAL_TIMESHEET_PERIODS:
        frappe.throw("Please select a valid timesheet period.")

    if status not in ("All", "Draft", "Submitted"):
        frappe.throw("Please select a valid timesheet status.")

    start_date, end_date = _get_portal_timesheet_date_range(period)
    response_data = {
        "setup_complete": False,
        "missing_setup": [],
        "filters": {"period": period, "status": status},
        "period": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "today_hours": 0,
            "period_hours": 0,
            "draft_timesheets": 0,
            "submitted_timesheets": 0,
            "active_session": None,
            "project_hours": [],
            "task_hours": [],
            "is_truncated": False,
        },
        "timesheets": [],
        "pagination": {
            "page": page,
            "page_length": page_length,
            "has_previous": page > 1,
            "has_more": False,
            "total_records": 0,
            "total_pages": 0,
            "is_truncated": False,
        },
    }

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name"],
        as_dict=True,
    )

    if not employee:
        response_data["missing_setup"] = [
            "Active Employee is not linked with logged-in User"
        ]
        frappe.response["message"] = response_data
        return

    response_data["setup_complete"] = True
    timesheet_filters = {
        "employee": employee.name,
        "start_date": ["between", [start_date, end_date]],
        "docstatus": ["<", 2],
    }

    if status == "Draft":
        timesheet_filters["docstatus"] = 0
    elif status == "Submitted":
        timesheet_filters["docstatus"] = 1

    timesheet_fields = [
        "name",
        "start_date",
        "end_date",
        "status",
        "docstatus",
        "total_hours",
        "modified",
    ]

    # Employee portal users may not have broad Desk read access to Timesheet. This query is safe
    # because the API already authenticated the user and constrains every returned row to their Employee.
    summary_rows = frappe.get_all(
        "Timesheet",
        filters=timesheet_filters,
        fields=timesheet_fields,
        order_by="start_date desc, modified desc",
        limit_page_length=501,
    )
    is_truncated = len(summary_rows) > 500

    if is_truncated:
        summary_rows = summary_rows[:500]

    total_records = len(summary_rows)
    total_pages = (total_records + page_length - 1) // page_length

    page = min(page, total_pages or 1)
    page_start = (page - 1) * page_length

    page_rows = summary_rows[page_start : page_start + page_length]
    # Do not expose an empty page after the bounded result set; truncation is reported separately.
    response_data["pagination"].update(
        {
            "page": page,
            "has_previous": page > 1,
            "has_more": total_records > page_start + page_length,
            "total_records": total_records,
            "total_pages": total_pages,
            "is_truncated": is_truncated,
        }
    )

    timesheet_names = [row.name for row in summary_rows]
    time_log_rows = []

    if timesheet_names:
        time_log_rows = frappe.get_all(
            "Timesheet Detail",
            filters={"parent": ["in", timesheet_names], "parenttype": "Timesheet"},
            fields=[
                "parent",
                "idx",
                "activity_type",
                "from_time",
                "to_time",
                "hours",
                "completed",
                "project",
                "task",
                "description",
            ],
            order_by="parent asc, idx asc",
            limit_page_length=5000,
        )

    task_names = sorted({row.task for row in time_log_rows if row.task})
    project_names = sorted({row.project for row in time_log_rows if row.project})
    task_label_map = {}
    project_label_map = {}

    if task_names:
        for task in frappe.db.get_list(
            "Task",
            filters={"name": ["in", task_names]},
            fields=["name", "subject"],
            limit_page_length=1000,
        ):
            task_label_map[task.name] = task.subject or task.name

    if project_names:
        for project in frappe.db.get_list(
            "Project",
            filters={"name": ["in", project_names]},
            fields=["name", "project_name"],
            limit_page_length=1000,
        ):
            project_label_map[project.name] = project.project_name or project.name

    time_logs_by_timesheet = {row.name: [] for row in summary_rows}
    project_hours = {}
    task_hours = {}
    today = frappe.utils.getdate(frappe.utils.today())
    now = frappe.utils.now_datetime()
    active_session = None
    today_hours = 0
    period_hours = 0

    for row in time_log_rows:
        is_running = bool(row.from_time and not row.to_time and not row.completed)
        duration_hours = frappe.utils.flt(row.hours)

        if is_running:
            duration_hours = max(
                frappe.utils.time_diff_in_seconds(now, row.from_time) / 3600,
                0,
            )

        project_key = row.project or ""
        task_key = row.task or ""
        project_hours[project_key] = project_hours.get(project_key, 0) + duration_hours
        task_hours[task_key] = task_hours.get(task_key, 0) + duration_hours
        period_hours += duration_hours

        if row.from_time and frappe.utils.getdate(row.from_time) == today:
            today_hours += duration_hours

        time_log_payload = {
            "activity_type": row.activity_type or "",
            "from_time": row.from_time,
            "to_time": row.to_time,
            "hours": duration_hours,
            "is_running": is_running,
            "project": project_key,
            "project_label": project_label_map.get(project_key) or project_key or "No Project",
            "task": task_key,
            "task_label": task_label_map.get(task_key) or task_key or "No Task",
            "description": frappe.utils.strip_html(row.description or ""),
        }
        time_logs_by_timesheet.setdefault(row.parent, []).append(time_log_payload)

        if is_running and not active_session:
            active_session = time_log_payload

    response_data["summary"].update(
        {
            "today_hours": today_hours,
            "period_hours": period_hours,
            "draft_timesheets": sum(row.docstatus == 0 for row in summary_rows),
            "submitted_timesheets": sum(row.docstatus == 1 for row in summary_rows),
            "active_session": active_session,
            "is_truncated": is_truncated,
            "project_hours": [
                {
                    "name": project_name or "No Project",
                    "label": project_label_map.get(project_name)
                    or project_name
                    or "No Project",
                    "hours": hours,
                }
                for project_name, hours in sorted(
                    project_hours.items(), key=lambda item: item[1], reverse=True
                )[:5]
            ],
            "task_hours": [
                {
                    "name": task_name or "No Task",
                    "label": task_label_map.get(task_name) or task_name or "No Task",
                    "hours": hours,
                }
                for task_name, hours in sorted(
                    task_hours.items(), key=lambda item: item[1], reverse=True
                )[:5]
            ],
        }
    )

    response_data["timesheets"] = [
        {
            "name": row.name,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "status": "Draft" if row.docstatus == 0 else "Submitted",
            "total_hours": sum(
                log["hours"] for log in time_logs_by_timesheet.get(row.name, [])
            ),
            "time_logs": time_logs_by_timesheet.get(row.name, []),
        }
        for row in page_rows
    ]

    frappe.response["message"] = response_data


@frappe.whitelist()
def employee_project_portal_get_task_board():
    # This returns the current user's assigned Tasks grouped client-side by configured status.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_meta = frappe.get_meta("Task")

    if not task_meta.has_field("custom_task_owner"):
        frappe.throw("Task field custom_task_owner is required for Task Board.")

    search = frappe.utils.cstr(frappe.form_dict.get("search") or "").strip()
    board_statuses = [
        status
        for status in _get_task_select_options(task_meta, "status")
        if status not in ("Template", "Cancelled")
    ]

    # Task has a standard status Select, but retain a useful board if a custom schema omits options.
    if not board_statuses:
        board_statuses = ["Open"]

    task_filters = {
        "custom_task_owner": user,
        "is_group": 0,
        "status": ["in", board_statuses],
    }
    task_or_filters = {}

    if search:
        search_value = "%{0}%".format(search)
        task_or_filters = {
            "name": ["like", search_value],
            "subject": ["like", search_value],
        }

    # A board needs all lanes in one response. Keep the response bounded and disclose truncation.
    board_limit = 500
    task_rows = frappe.db.get_list(
        "Task",
        filters=task_filters,
        or_filters=task_or_filters,
        fields=_get_portal_task_fields(task_meta),
        order_by="exp_end_date asc, modified desc",
        limit_page_length=board_limit + 1,
    )
    is_truncated = len(task_rows) > board_limit

    if is_truncated:
        task_rows = task_rows[:board_limit]

    today_date = frappe.utils.getdate(frappe.utils.today())
    tasks = []

    for task_row in task_rows:
        due_date = task_row.get("exp_end_date")
        is_overdue = bool(
            due_date
            and task_row.status not in PORTAL_CLOSED_TASK_STATUSES
            and frappe.utils.getdate(due_date) < today_date
        )

        tasks.append(
            {
                "name": task_row.name,
                "subject": task_row.subject or task_row.name,
                "project": task_row.project or "",
                "status": task_row.status or "Open",
                "priority": task_row.get("priority") or "",
                "due_date": due_date,
                "progress": task_row.get("progress") or 0,
                "expected_time": task_row.get("expected_time") or 0,
                "actual_time": task_row.get("actual_time") or 0,
                "is_overdue": is_overdue,
            }
        )

    frappe.response["message"] = {
        "filters": {"search": search},
        "statuses": board_statuses,
        "tasks": tasks,
        "active_work": _get_portal_active_work_session(user),
        "is_truncated": is_truncated,
        "board_limit": board_limit,
    }


@frappe.whitelist()
def employee_project_portal_start_my_task_work():
    # This starts one owned Task through the existing Employee Portal Timesheet flow.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_name = frappe.utils.cstr(frappe.form_dict.get("task") or "").strip()

    if not task_name:
        frappe.throw("Please select a Task.")

    task_meta = frappe.get_meta("Task")
    task_doc = _get_owned_portal_task_for_work(user, task_name, task_meta)

    if task_doc.status in PORTAL_CLOSED_TASK_STATUSES:
        frappe.throw("Completed or cancelled Tasks cannot be started.")

    status_options = set(_get_task_select_options(task_meta, "status"))

    if "Working" not in status_options:
        frappe.throw("Task status Working is required before work can be started.")

    # The shared helper performs attendance checks, validates the Task/Project,
    # ensures only one session runs, and persists through normal Timesheet hooks.
    response_data = _start_employee_work_session(
        user=user,
        project=task_doc.project or "",
        task=task_doc.name,
    )

    # Employees normally lack Task write permission. This owner-scoped endpoint
    # re-checks ownership, changes only status, and still runs normal Task hooks.
    if task_doc.custom_task_owner != user:
        frappe.throw("Task Owner changed. Refresh the task before continuing.")

    if task_doc.status != "Working":
        task_doc.status = "Working"
        task_doc.save(ignore_permissions=True)

    frappe.response["message"] = response_data


@frappe.whitelist()
def employee_project_portal_stop_my_task_work():
    # This can stop only the active session that belongs to the selected owned Task.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_name = frappe.utils.cstr(frappe.form_dict.get("task") or "").strip()

    if not task_name:
        frappe.throw("Please select a Task.")

    task_meta = frappe.get_meta("Task")
    _get_owned_portal_task_for_work(user, task_name, task_meta)

    frappe.response["message"] = _stop_employee_work_session(
        user, expected_task=task_name
    )


@frappe.whitelist()
def employee_project_portal_add_task_update():
    # This adds an auditable progress update without overwriting Task description.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_name = frappe.utils.cstr(frappe.form_dict.get("task") or "").strip()

    if not task_name:
        frappe.throw("Please select a Task.")

    task_meta = frappe.get_meta("Task")
    task_doc = _get_owned_portal_task_for_work(user, task_name, task_meta)
    work_completed = _clean_portal_task_update_text(
        frappe.form_dict.get("work_completed"),
        "Work completed",
        PORTAL_TASK_UPDATE_MAX_LENGTH,
        required=True,
    )
    blocker = _clean_portal_task_update_text(
        frappe.form_dict.get("blocker"),
        "Blocker",
        PORTAL_TASK_UPDATE_OPTIONAL_FIELD_MAX_LENGTH,
    )
    next_step = _clean_portal_task_update_text(
        frappe.form_dict.get("next_step"),
        "Next step",
        PORTAL_TASK_UPDATE_OPTIONAL_FIELD_MAX_LENGTH,
    )

    status = frappe.utils.cstr(frappe.form_dict.get("status") or "").strip()
    progress_value = frappe.form_dict.get("progress")
    has_task_changes = False

    if status:
        status_options = set(_get_task_select_options(task_meta, "status"))

        if status not in status_options or status == "Template":
            frappe.throw("Please select a valid Task status.")

        if task_doc.status != status:
            task_doc.status = status
            has_task_changes = True

    if progress_value not in (None, ""):
        progress = frappe.utils.flt(progress_value)

        if progress < 0 or progress > 100:
            frappe.throw("Task progress must be between 0 and 100.")

        if frappe.utils.flt(task_doc.progress) != progress:
            task_doc.progress = progress
            has_task_changes = True

    # Mirror the existing owner-edit endpoint when an update completes a Task.
    if task_doc.status == "Completed" and not task_doc.completed_on:
        task_doc.completed_on = frappe.utils.today()
        has_task_changes = True

    if has_task_changes:
        # The endpoint already enforced portal role and ownership before this scoped save.
        task_doc.save(ignore_permissions=True)

    update_sections = ["Work completed:\n{0}".format(work_completed)]

    if blocker:
        update_sections.append("Blocker:\n{0}".format(blocker))

    if next_step:
        update_sections.append("Next step:\n{0}".format(next_step))

    comment = task_doc.add_comment(
        "Comment",
        text="\n\n".join(update_sections),
        comment_email=user,
        comment_by=get_fullname(user),
    )

    if blocker:
        _notify_portal_project_managers_about_blocker(task_doc, blocker, user)

    frappe.response["message"] = {
        "success": True,
        "update": {"name": comment.name},
        "task": _get_my_task_detail_payload(task_doc, task_meta, user),
    }


@frappe.whitelist()
def employee_project_portal_get_notifications():
    # This exposes only the logged-in user's Shayona portal alerts.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)
    frappe.response["message"] = _get_project_portal_notifications(user)


@frappe.whitelist(methods=["POST"])
def employee_project_portal_mark_notifications_read():
    # This mirrors Frappe's standard bulk read update, scoped to the portal app.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)
    frappe.db.set_value(
        "Notification Log",
        {"for_user": user, "app": PORTAL_NOTIFICATION_APP, "read": 0},
        "read",
        1,
        update_modified=False,
    )
    frappe.response["message"] = {"unread_count": 0}


@frappe.whitelist(methods=["POST"])
def employee_project_portal_upload_task_attachment():
    # This keeps website users within the Task-owner boundary that generic File upload cannot provide.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_name = frappe.utils.cstr(frappe.form_dict.get("task") or "").strip()

    if not task_name:
        frappe.throw("Please select a Task.")

    task_meta = frappe.get_meta("Task")
    _get_owned_portal_task_for_work(user, task_name, task_meta)

    uploaded_file = frappe.request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        frappe.throw("Please select an attachment.")

    file_name = os.path.basename(frappe.utils.cstr(uploaded_file.filename)).strip()

    if not file_name:
        frappe.throw("Please select a valid attachment.")

    mime_type = mimetypes.guess_type(file_name)[0]

    if mime_type not in ALLOWED_MIMETYPES:
        frappe.throw(
            "Only images, PDF, TXT, CSV, Microsoft Office, and supported video files can be attached."
        )

    max_file_size = get_max_file_size()
    content = uploaded_file.stream.read(max_file_size + 1)

    if len(content) > max_file_size:
        frappe.throw(
            "Attachment exceeds the maximum allowed size of {0} MB.".format(
                frappe.utils.flt(max_file_size / (1024 * 1024), 1)
            )
        )

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "attached_to_doctype": "Task",
            "attached_to_name": task_name,
            "file_name": file_name,
            "is_private": 1,
            "content": content,
        }
    ).insert(ignore_permissions=True)

    frappe.response["message"] = {
        "success": True,
        "attachment": {
            "name": file_doc.name,
            "file_name": file_doc.file_name,
            "file_url": file_doc.file_url,
            "created_at": file_doc.creation,
        },
    }


@frappe.whitelist()
def employee_project_portal_get_task_details():
    # This returns one owned Task for the portal detail drawer and its edit controls.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_name = frappe.utils.cstr(frappe.form_dict.get("task") or "").strip()

    if not task_name:
        frappe.throw("Please select a Task.")

    task_meta = frappe.get_meta("Task")

    if not task_meta.has_field("custom_task_owner"):
        frappe.throw("Task field custom_task_owner is required for My Tasks.")

    # This repeats the list ownership filter so direct API calls cannot open another user's task.
    task_rows = frappe.db.get_list(
        "Task",
        filters={"name": task_name, "custom_task_owner": user, "is_group": 0},
        fields=_get_portal_task_fields(task_meta),
        limit_page_length=1,
    )

    if not task_rows:
        frappe.throw("Task does not exist or you do not have permission.")

    frappe.response["message"] = {
        "task": _get_my_task_detail_payload(task_rows[0], task_meta, user)
    }


@frappe.whitelist()
def employee_project_portal_update_my_task():
    # This updates one owned Task while allowing only the portal fields approved for the user's role.
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    require_project_portal_access(user)

    task_name = frappe.utils.cstr(frappe.form_dict.get("task") or "").strip()

    if not task_name:
        frappe.throw("Please select a Task.")

    task_meta = frappe.get_meta("Task")

    if not task_meta.has_field("custom_task_owner"):
        frappe.throw("Task field custom_task_owner is required for My Tasks.")

    # This lookup checks ownership before loading the document, so another user's Task cannot be edited.
    task_rows = frappe.db.get_list(
        "Task",
        filters={"name": task_name, "custom_task_owner": user, "is_group": 0},
        fields=["name"],
        limit_page_length=1,
    )

    if not task_rows:
        frappe.throw("Task does not exist or you do not have permission.")

    task_doc = frappe.get_doc("Task", task_name)

    # This re-check protects the small window between the permission query and document save.
    if task_doc.custom_task_owner != user:
        frappe.throw("Task Owner changed. Refresh the task before saving again.")

    editable_fields = set(_get_portal_task_editable_fields(user, task_meta))
    requested_fields = {
        fieldname
        for fieldname in (
            PORTAL_TASK_OWNER_EDIT_FIELDS | PORTAL_TASK_MANAGER_EDIT_FIELDS
        )
        if fieldname in frappe.form_dict
    }
    restricted_fields = requested_fields - editable_fields

    if restricted_fields:
        frappe.throw(
            "You do not have permission to update: {0}.".format(
                ", ".join(sorted(restricted_fields))
            )
        )

    if not requested_fields:
        frappe.throw("Please change at least one Task field.")

    status_options = set(_get_task_select_options(task_meta, "status"))
    priority_options = set(_get_task_select_options(task_meta, "priority"))

    if "subject" in requested_fields:
        subject = frappe.utils.cstr(frappe.form_dict.get("subject") or "").strip()

        if not subject:
            frappe.throw("Task Title is required.")

        task_doc.subject = subject

    if "status" in requested_fields:
        status = frappe.utils.cstr(frappe.form_dict.get("status") or "").strip()

        if not status or status not in status_options or status == "Template":
            frappe.throw("Please select a valid Task status.")

        task_doc.status = status

    if "priority" in requested_fields:
        priority = frappe.utils.cstr(frappe.form_dict.get("priority") or "").strip()

        if priority and priority not in priority_options:
            frappe.throw("Please select a valid Task priority.")

        task_doc.priority = priority or None

    if "type" in requested_fields:
        task_type = frappe.utils.cstr(frappe.form_dict.get("type") or "").strip()

        if task_type:
            task_type_rows = frappe.db.get_list(
                "Task Type",
                filters={"name": task_type},
                fields=["name"],
                limit_page_length=1,
            )

            if not task_type_rows:
                frappe.throw("Task Type does not exist or you do not have permission.")

        task_doc.type = task_type or None

    if "description" in requested_fields:
        task_doc.description = frappe.utils.cstr(
            frappe.form_dict.get("description") or ""
        )

    for fieldname in ("exp_start_date", "exp_end_date"):
        if fieldname not in requested_fields:
            continue

        date_value = frappe.utils.cstr(frappe.form_dict.get(fieldname) or "").strip()
        task_doc.set(
            fieldname, frappe.utils.get_datetime(date_value) if date_value else None
        )

    if "progress" in requested_fields:
        progress = frappe.utils.flt(frappe.form_dict.get("progress") or 0)

        if progress < 0 or progress > 100:
            frappe.throw("Task progress must be between 0 and 100.")

        task_doc.progress = progress

    if "expected_time" in requested_fields:
        expected_time = frappe.utils.flt(frappe.form_dict.get("expected_time") or 0)

        if expected_time < 0:
            frappe.throw("Expected Time cannot be negative.")

        task_doc.expected_time = expected_time

    if "custom_task_owner" in requested_fields:
        task_owner = frappe.utils.cstr(
            frappe.form_dict.get("custom_task_owner") or ""
        ).strip()

        if not task_owner:
            frappe.throw("Task Owner is required.")

        _validate_portal_task_owner(task_owner)
        task_doc.custom_task_owner = task_owner

    # This mirrors Desk behavior: completing a Task records today when no completion date exists.
    if task_doc.status == "Completed" and not task_doc.completed_on:
        task_doc.completed_on = frappe.utils.today()

    # Employees lack generic Task write permission. This narrow endpoint enforces role, ownership,
    # active-owner validation, and an explicit field whitelist before running normal Task hooks.
    task_doc.save(ignore_permissions=True)

    ownership_transferred = task_doc.custom_task_owner != user

    frappe.response["message"] = {
        "success": True,
        "ownership_transferred": ownership_transferred,
        "task": _get_my_task_detail_payload(task_doc, task_meta, user),
    }

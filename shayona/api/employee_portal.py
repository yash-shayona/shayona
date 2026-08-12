import frappe
from frappe import _
from frappe.utils import flt, get_datetime, getdate, now_datetime, get_fullname


@frappe.whitelist()
def employee_portal_get_boot_data():
    # API Method:
    # employee_portal_get_boot_data

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    # ---------------------------------------------------------
    # Logged-in Employee
    # ---------------------------------------------------------

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "company", "department"],
        as_dict=True,
    )

    allow_geolocation_tracking = (
        frappe.db.get_single_value("HR Settings", "allow_geolocation_tracking") or 0
    )

    selected_project = frappe.form_dict.get("project") or ""

    # ---------------------------------------------------------
    # Default Boot Response
    # ---------------------------------------------------------

    boot_data = {
        "setup_complete": False,
        "missing_setup": [],
        "allow_geolocation_tracking": (1 if allow_geolocation_tracking else 0),
        "user": {
            "email": user,
            "employee": "",
            "employee_name": frappe.utils.get_fullname(user),
            "company": "",
            "department": "",
        },
        "status": "Not Started",
        "entry_time": None,
        "exit_time": None,
        "completed_work_seconds": 0,
        "completed_break_seconds": 0,
        "active_work_started_at": None,
        "active_break_started_at": None,
        "total_work_hours": 0,
        "total_break_hours": 0,
        "timesheet_name": None,
        "projects": [],
        "tasks": [],
        "activity_types": [],
        "task_types": [],
        "selected_values": {
            "project": selected_project,
            "task": "",
            "activity_type": "",
            "description": "",
        },
        "current_work_session": None,
        "work_sessions": [],
        "break_logs": [],
    }

    # ---------------------------------------------------------
    # Employee Setup
    # ---------------------------------------------------------

    if not employee:
        boot_data["missing_setup"] = [
            "Active Employee is not linked with logged-in User"
        ]

    else:
        boot_data["setup_complete"] = True

        boot_data["user"] = {
            "email": user,
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "company": employee.company,
            "department": employee.department,
        }

        # -----------------------------------------------------
        # Permission-wise Projects
        # -----------------------------------------------------

        project_rows = frappe.db.get_list(
            "Project",
            filters={"status": "Open"},
            fields=["name", "project_name"],
            order_by="project_name asc",
            limit_page_length=500,
        )

        projects = []

        for project_row in project_rows:
            projects.append(
                {
                    "value": project_row.name,
                    "label": (project_row.project_name or project_row.name),
                }
            )

        boot_data["projects"] = projects

        # -----------------------------------------------------
        # Permission-wise Tasks
        # -----------------------------------------------------

        task_rows = []
        
        if selected_project:
            task_filters = {
                "status": ["not in", ["Cancelled", "Completed"]],
                "is_group": 0,
            }

            task_filters["project"] = selected_project

            task_rows = frappe.db.get_list(
                "Task",
                filters=task_filters,
                fields=["name", "subject", "project", "status"],
                order_by="subject asc",
                limit_page_length=500,
            )

        tasks = []

        for task_row in task_rows:
            tasks.append(
                {
                    "value": task_row.name,
                    "label": (task_row.subject or task_row.name),
                    "project": task_row.project,
                    "status": task_row.status,
                }
            )

        boot_data["tasks"] = tasks

        # -----------------------------------------------------
        # Permission-wise Activity Types
        # -----------------------------------------------------

        activity_type_rows = frappe.db.get_list(
            "Activity Type", fields=["name"], order_by="name asc", limit_page_length=500
        )

        activity_types = []

        for activity_row in activity_type_rows:
            activity_types.append(
                {"value": activity_row.name, "label": activity_row.name}
            )

        boot_data["activity_types"] = activity_types

        # -----------------------------------------------------
        # Permission-wise Task Types
        # -----------------------------------------------------

        task_type_rows = frappe.db.get_list(
            "Task Type", fields=["name"], order_by="name asc", limit_page_length=500
        )

        task_types = []

        for task_type_row in task_type_rows:
            task_types.append(
                {"value": task_type_row.name, "label": task_type_row.name}
            )

        boot_data["task_types"] = task_types

        # -----------------------------------------------------
        # Today
        # -----------------------------------------------------

        today = frappe.utils.today()

        day_start = today + " 00:00:00"
        day_end = today + " 23:59:59"

        # -----------------------------------------------------
        # Employee Checkins
        # -----------------------------------------------------

        checkins = frappe.db.get_all(
            "Employee Checkin",
            filters={
                "employee": employee.name,
                "time": ["between", [day_start, day_end]],
            },
            fields=[
                "name",
                "time",
                "creation",
                "log_type",
                "custom_action_type",
                "shift",
            ],
            order_by="time asc, creation asc",
            limit_page_length=200,
        )

        # -----------------------------------------------------
        # Attendance Status
        # -----------------------------------------------------

        status = "Not Started"
        entry_time = None
        exit_time = None

        work_started_at = None
        break_started_at = None

        completed_work_seconds = 0
        completed_break_seconds = 0

        break_logs = []
        open_break = None
        break_number = 0

        for checkin in checkins:
            action_type = checkin.custom_action_type

            if action_type == "Entry":
                if not entry_time:
                    entry_time = checkin.time

                work_started_at = checkin.time
                break_started_at = None
                status = "Day Started"

            elif action_type == "Break Start":
                if work_started_at:
                    work_seconds = frappe.utils.time_diff_in_seconds(
                        checkin.time, work_started_at
                    )

                    if work_seconds > 0:
                        completed_work_seconds = completed_work_seconds + work_seconds

                work_started_at = None
                break_started_at = checkin.time
                status = "On Break"

                break_number = break_number + 1

                open_break = {
                    "break_number": break_number,
                    "break_start": checkin.time,
                    "break_end": None,
                    "duration_hours": 0,
                    "status": "Open",
                }

            elif action_type == "Break End":
                if break_started_at:
                    break_seconds = frappe.utils.time_diff_in_seconds(
                        checkin.time, break_started_at
                    )

                    if break_seconds < 0:
                        break_seconds = 0

                    completed_break_seconds = completed_break_seconds + break_seconds

                    if open_break:
                        open_break["break_end"] = checkin.time

                        open_break["duration_hours"] = break_seconds / 3600

                        open_break["status"] = "Completed"

                        break_logs.append(open_break)

                open_break = None
                break_started_at = None
                work_started_at = checkin.time
                status = "Day Started"

            elif action_type == "Exit":
                exit_time = checkin.time

                if work_started_at:
                    work_seconds = frappe.utils.time_diff_in_seconds(
                        checkin.time, work_started_at
                    )

                    if work_seconds > 0:
                        completed_work_seconds = completed_work_seconds + work_seconds

                elif break_started_at:
                    break_seconds = frappe.utils.time_diff_in_seconds(
                        checkin.time, break_started_at
                    )

                    if break_seconds < 0:
                        break_seconds = 0

                    completed_break_seconds = completed_break_seconds + break_seconds

                    if open_break:
                        open_break["break_end"] = checkin.time

                        open_break["duration_hours"] = break_seconds / 3600

                        open_break["status"] = "Completed"

                        break_logs.append(open_break)

                work_started_at = None
                break_started_at = None
                open_break = None
                status = "Day Ended"

        # -----------------------------------------------------
        # Running Break
        # -----------------------------------------------------

        if open_break:
            running_break_seconds = frappe.utils.time_diff_in_seconds(
                frappe.utils.now_datetime(), open_break["break_start"]
            )

            if running_break_seconds < 0:
                running_break_seconds = 0

            open_break["duration_hours"] = running_break_seconds / 3600

            break_logs.append(open_break)

        # -----------------------------------------------------
        # Today's Timesheet
        # -----------------------------------------------------

        timesheet_rows = frappe.db.get_all(
            "Timesheet",
            filters={
                "employee": employee.name,
                "start_date": today,
                "docstatus": ["<", 2],
            },
            fields=["name", "docstatus", "start_date", "end_date"],
            order_by="creation desc",
            limit_page_length=2,
        )

        current_work_session = None
        work_sessions = []

        if timesheet_rows:
            timesheet_name = timesheet_rows[0].name

            boot_data["timesheet_name"] = timesheet_name

            timesheet = frappe.get_doc("Timesheet", timesheet_name)

            task_names = []
            project_names = []

            for row in timesheet.time_logs:
                if row.task and row.task not in task_names:
                    task_names.append(row.task)

                if row.project and row.project not in project_names:
                    project_names.append(row.project)

            # -------------------------------------------------
            # Task Labels
            # -------------------------------------------------

            task_label_map = {}

            if task_names:
                visible_tasks = frappe.db.get_list(
                    "Task",
                    filters={"name": ["in", task_names]},
                    fields=["name", "subject"],
                    limit_page_length=500,
                )

                for visible_task in visible_tasks:
                    task_label_map[visible_task.name] = (
                        visible_task.subject or visible_task.name
                    )

            # -------------------------------------------------
            # Project Labels
            # -------------------------------------------------

            project_label_map = {}

            if project_names:
                visible_projects = frappe.db.get_list(
                    "Project",
                    filters={"name": ["in", project_names]},
                    fields=["name", "project_name"],
                    limit_page_length=500,
                )

                for visible_project in visible_projects:
                    project_label_map[visible_project.name] = (
                        visible_project.project_name or visible_project.name
                    )

            # -------------------------------------------------
            # Work Sessions
            # -------------------------------------------------

            for row in timesheet.time_logs:
                duration_hours = row.hours or 0

                is_running = not row.completed and row.from_time and not row.to_time

                if is_running:
                    running_seconds = frappe.utils.time_diff_in_seconds(
                        frappe.utils.now_datetime(), row.from_time
                    )

                    if running_seconds < 0:
                        running_seconds = 0

                    duration_hours = running_seconds / 3600

                elif row.from_time and row.to_time:
                    session_seconds = frappe.utils.time_diff_in_seconds(
                        row.to_time, row.from_time
                    )

                    if session_seconds < 0:
                        session_seconds = 0

                    duration_hours = session_seconds / 3600

                session = {
                    "name": row.name,
                    "timesheet": timesheet.name,
                    "project": row.project,
                    "project_label": (
                        project_label_map.get(row.project) or row.project or ""
                    ),
                    "task": row.task,
                    "task_label": (task_label_map.get(row.task) or row.task or ""),
                    "activity_type": (row.activity_type or ""),
                    "description": (row.description or ""),
                    "from_time": row.from_time,
                    "to_time": row.to_time,
                    "duration_hours": (duration_hours),
                    "completed": (row.completed or 0),
                }

                work_sessions.append(session)

                if is_running:
                    current_work_session = session

        # -----------------------------------------------------
        # Final Status
        # -----------------------------------------------------

        if current_work_session and status == "Day Started":
            status = "Working"

        # -----------------------------------------------------
        # Form Selected Values
        # Only current running row can prefill the form.
        # Previous completed row must not prefill.
        # -----------------------------------------------------

        if current_work_session:
            boot_data["selected_values"] = {
                "project": (current_work_session["project"] or ""),
                "task": (current_work_session["task"] or ""),
                "activity_type": (current_work_session["activity_type"] or ""),
                "description": (current_work_session["description"] or ""),
            }

        else:
            boot_data["selected_values"] = {
                "project": selected_project,
                "task": "",
                "activity_type": "",
                "description": "",
            }

        # -----------------------------------------------------
        # Final Response Values
        # -----------------------------------------------------

        boot_data["status"] = status
        boot_data["entry_time"] = entry_time
        boot_data["exit_time"] = exit_time

        boot_data["completed_work_seconds"] = completed_work_seconds

        boot_data["completed_break_seconds"] = completed_break_seconds

        boot_data["active_work_started_at"] = work_started_at

        boot_data["active_break_started_at"] = break_started_at

        boot_data["total_work_hours"] = completed_work_seconds / 3600

        boot_data["total_break_hours"] = completed_break_seconds / 3600

        boot_data["current_work_session"] = current_work_session

        boot_data["work_sessions"] = work_sessions

        boot_data["break_logs"] = break_logs

    frappe.response["message"] = boot_data


@frappe.whitelist()
def employee_portal_start_day():
    # Employee Portal - Start Day / Entry
    # Creates one Employee Checkin with:
    # log_type = IN
    # custom_action_type = Entry

    if frappe.session.user == "Guest":
        frappe.throw("Please login to continue.")

    # Never accept Employee from browser.
    # Always resolve Employee from the logged-in user.
    employee = frappe.db.get_value(
        "Employee",
        {"user_id": frappe.session.user, "status": "Active"},
        ["name", "employee_name"],
        as_dict=True,
    )

    if not employee:
        frappe.throw(
            "No active Employee is linked with user {0}.".format(frappe.session.user)
        )

    today = frappe.utils.today()
    day_start = today + " 00:00:00"
    day_end = today + " 23:59:59"

    # Prevent repeated Entry clicks from creating multiple Entry records.
    existing_entry = frappe.db.exists(
        "Employee Checkin",
        {
            "employee": employee.name,
            "custom_action_type": "Entry",
            "time": ["between", [day_start, day_end]],
        },
    )

    if existing_entry:
        frappe.throw("Your Entry is already recorded for today.")

    # Coordinates will be sent by the browser when available.
    latitude = frappe.form_dict.get("latitude")
    longitude = frappe.form_dict.get("longitude")

    checkin = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "log_type": "IN",
            "time": frappe.utils.now_datetime(),
            "custom_action_type": "Entry",
            "latitude": latitude,
            "longitude": longitude,
        }
    )

    checkin.insert()

    frappe.response["message"] = {
        "success": True,
        "checkin_name": checkin.name,
        "employee": checkin.employee,
        "employee_name": checkin.employee_name,
        "log_type": checkin.log_type,
        "custom_action_type": checkin.custom_action_type,
        "time": checkin.time,
        "shift": checkin.shift,
        "offshift": checkin.offshift,
    }


@frappe.whitelist()
def employee_portal_start_break():
    # employee_portal_start_break

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name"],
        as_dict=True,
    )

    if not employee:
        frappe.throw("No active Employee is linked with this User.")

    today = frappe.utils.today()
    day_start = today + " 00:00:00"
    day_end = today + " 23:59:59"

    latest_rows = frappe.db.get_all(
        "Employee Checkin",
        filters={"employee": employee.name, "time": ["between", [day_start, day_end]]},
        fields=["name", "time", "creation", "log_type", "custom_action_type"],
        order_by="time desc, creation desc",
        limit_page_length=1,
    )

    latest_checkin = latest_rows[0] if latest_rows else None
    latest_action = latest_checkin.custom_action_type if latest_checkin else None

    if latest_action not in ["Entry", "Break End"]:
        frappe.throw("Break can only be started after Entry or Break End.")

    # ---------------------------------------------------------
    # Close current Timesheet session before Break Start
    # ---------------------------------------------------------

    today = frappe.utils.today()

    timesheet_rows = frappe.db.get_all(
        "Timesheet",
        filters={"employee": employee.name, "start_date": today, "docstatus": 0},
        fields=["name"],
        order_by="creation desc",
        limit_page_length=1,
    )

    if timesheet_rows:
        timesheet = frappe.get_doc("Timesheet", timesheet_rows[0].name)

        open_row = None

        for row in timesheet.time_logs:
            if not row.completed:
                open_row = row

        if open_row:
            open_row.to_time = frappe.utils.now_datetime()
            open_row.completed = 1

            timesheet.save()

    checkin = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "time": frappe.utils.now_datetime(),
            "log_type": "OUT",
            "custom_action_type": "Break Start",
            "latitude": frappe.form_dict.get("latitude"),
            "longitude": frappe.form_dict.get("longitude"),
        }
    )

    checkin.insert()

    frappe.response["message"] = {
        "success": True,
        "name": checkin.name,
        "time": checkin.time,
    }


@frappe.whitelist()
def employee_portal_end_break():
    # employee_portal_end_break

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name"],
        as_dict=True,
    )

    if not employee:
        frappe.throw("No active Employee is linked with this User.")

    today = frappe.utils.today()
    day_start = today + " 00:00:00"
    day_end = today + " 23:59:59"

    latest_rows = frappe.db.get_all(
        "Employee Checkin",
        filters={"employee": employee.name, "time": ["between", [day_start, day_end]]},
        fields=["name", "time", "creation", "log_type", "custom_action_type"],
        order_by="time desc, creation desc",
        limit_page_length=1,
    )

    latest_checkin = latest_rows[0] if latest_rows else None
    latest_action = latest_checkin.custom_action_type if latest_checkin else None

    if latest_action != "Break Start":
        frappe.throw("There is no active break to end.")

    checkin = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "time": frappe.utils.now_datetime(),
            "log_type": "IN",
            "custom_action_type": "Break End",
            "latitude": frappe.form_dict.get("latitude"),
            "longitude": frappe.form_dict.get("longitude"),
        }
    )

    checkin.insert()

    frappe.response["message"] = {
        "success": True,
        "name": checkin.name,
        "time": checkin.time,
    }


@frappe.whitelist()
def employee_portal_end_day():
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name"],
        as_dict=True,
    )

    if not employee:
        frappe.throw("No active Employee is linked with this User.")

    today = frappe.utils.today()
    day_start = today + " 00:00:00"
    day_end = today + " 23:59:59"

    latest_rows = frappe.db.get_all(
        "Employee Checkin",
        filters={"employee": employee.name, "time": ["between", [day_start, day_end]]},
        fields=["name", "time", "creation", "log_type", "custom_action_type"],
        order_by="time desc, creation desc",
        limit_page_length=1,
    )

    latest_checkin = latest_rows[0] if latest_rows else None
    latest_action = latest_checkin.custom_action_type if latest_checkin else None

    if latest_action == "Break Start":
        frappe.throw("Please end your break before exiting.")

    if latest_action not in ["Entry", "Break End"]:
        frappe.throw("Day cannot be ended in the current state.")

    # ---------------------------------------------------------
    # Close current Timesheet session before Exit
    # ---------------------------------------------------------

    today = frappe.utils.today()

    timesheet_rows = frappe.db.get_all(
        "Timesheet",
        filters={"employee": employee.name, "start_date": today, "docstatus": 0},
        fields=["name"],
        order_by="creation desc",
        limit_page_length=1,
    )

    if timesheet_rows:
        timesheet = frappe.get_doc("Timesheet", timesheet_rows[0].name)

        open_row = None

        for row in timesheet.time_logs:
            if not row.completed:
                open_row = row

        if open_row:
            open_row.to_time = frappe.utils.now_datetime()
            open_row.completed = 1

            timesheet.save()

    checkin = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": employee.name,
            "employee_name": employee.employee_name,
            "time": frappe.utils.now_datetime(),
            "log_type": "OUT",
            "custom_action_type": "Exit",
            "latitude": frappe.form_dict.get("latitude"),
            "longitude": frappe.form_dict.get("longitude"),
        }
    )

    checkin.insert()

    frappe.response["message"] = {
        "success": True,
        "name": checkin.name,
        "time": checkin.time,
    }


@frappe.whitelist()
def employee_portal_start_work():
    frappe.response["message"] = _start_employee_work_session(
        user=frappe.session.user,
        project=frappe.form_dict.get("project"),
        task=frappe.form_dict.get("task"),
        activity_type=frappe.form_dict.get("activity_type"),
        description=frappe.form_dict.get("description"),
    )


def _start_employee_work_session(
    user, project="", task="", activity_type="", description=""
):
    # This shared helper keeps every portal entry point on the same attendance,
    # permission, and Timesheet lifecycle path.

    if user == "Guest":
        frappe.throw("Please login to continue.")

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "company"],
        as_dict=True,
    )

    if not employee:
        frappe.throw("No active Employee is linked with this User.")

    project = (project or "").strip()

    task = (task or "").strip()

    activity_type = (activity_type or "").strip()

    description = (description or "").strip()

    # At least one work-related value is required.
    if not (project or task or activity_type or description):
        frappe.throw(
            "Please select a Project, Task, " "Activity Type, or enter a Description."
        )

    # ---------------------------------------------------------
    # Attendance validation
    # ---------------------------------------------------------

    today = frappe.utils.today()
    day_start = today + " 00:00:00"
    day_end = today + " 23:59:59"

    latest_checkins = frappe.db.get_all(
        "Employee Checkin",
        filters={"employee": employee.name, "time": ["between", [day_start, day_end]]},
        fields=["name", "custom_action_type", "time"],
        order_by="time desc",
        limit_page_length=1,
    )

    if not latest_checkins:
        frappe.throw("Please record Entry before starting work.")

    latest_action = latest_checkins[0].custom_action_type

    if latest_action == "Break Start":
        frappe.throw("Please end your break before starting work.")

    if latest_action == "Exit":
        frappe.throw("Your work day has already ended.")

    if latest_action not in ["Entry", "Break End"]:
        frappe.throw("Work cannot be started in the current state.")

    # ---------------------------------------------------------
    # Permission-wise Activity Type validation
    # ---------------------------------------------------------

    if activity_type:
        activity_rows = frappe.db.get_list(
            "Activity Type",
            filters={"name": activity_type},
            fields=["name"],
            limit_page_length=1,
        )

        if not activity_rows:
            frappe.throw(
                "Activity Type does not exist " "or you do not have permission."
            )

    # ---------------------------------------------------------
    # Permission-wise Project validation
    # ---------------------------------------------------------

    if project:
        project_rows = frappe.db.get_list(
            "Project", filters={"name": project}, fields=["name"], limit_page_length=1
        )

        if not project_rows:
            frappe.throw("Project does not exist or you do not have permission.")

    # ---------------------------------------------------------
    # Permission-wise Task validation
    # ---------------------------------------------------------

    if task:
        task_rows = frappe.db.get_list(
            "Task",
            filters={"name": task, "status": ["!=", "Cancelled"], "is_group": 0},
            fields=["name", "subject", "project"],
            limit_page_length=1,
        )

        if not task_rows:
            frappe.throw("Task does not exist or you do not have permission.")

        task_project = task_rows[0].project or ""

        if not project and task_project:
            project = task_project

        elif project and task_project and project != task_project:
            frappe.throw("Selected Task does not belong to selected Project.")

    # ---------------------------------------------------------
    # Find today's Timesheet
    # ---------------------------------------------------------

    timesheet_rows = frappe.db.get_all(
        "Timesheet",
        filters={"employee": employee.name, "start_date": today, "docstatus": ["<", 2]},
        fields=["name", "docstatus"],
        order_by="creation desc",
        limit_page_length=2,
    )

    timesheet = None

    if timesheet_rows:
        if timesheet_rows[0].docstatus != 0:
            frappe.throw("Today's Timesheet is already submitted.")

        timesheet = frappe.get_doc("Timesheet", timesheet_rows[0].name)

        for row in timesheet.time_logs:
            if not row.completed:
                frappe.throw("A work session is already running. Use Switch Task.")

    now = frappe.utils.now_datetime()

    # ---------------------------------------------------------
    # Create or update Timesheet
    # ---------------------------------------------------------

    if not timesheet:
        timesheet = frappe.get_doc(
            {
                "doctype": "Timesheet",
                "employee": employee.name,
                "user": user,
                "company": employee.company,
                "start_date": today,
                "end_date": today,
                "time_logs": [
                    {
                        "activity_type": activity_type or None,
                        "project": project or None,
                        "task": task or None,
                        "description": description,
                        # Same From/To initially keeps draft valid.
                        # completed=0 means session is running.
                        "from_time": now,
                        "completed": 0,
                    }
                ],
            }
        )

        timesheet.insert()

    else:
        timesheet.append(
            "time_logs",
            {
                "activity_type": activity_type or None,
                "project": project or None,
                "task": task or None,
                "description": description,
                "from_time": now,
                "completed": 0,
            },
        )

        timesheet.save()

    return {"success": True, "timesheet": timesheet.name}


@frappe.whitelist()
def employee_portal_switch_task():
    frappe.response["message"] = _stop_employee_work_session(frappe.session.user)


def _stop_employee_work_session(user, expected_task=""):
    # This is named for the existing switch-task API, but it only closes the
    # currently running row. expected_task prevents a task-scoped UI from
    # stopping a different task's session.

    if user == "Guest":
        frappe.throw("Please login to continue.")

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "company"],
        as_dict=True,
    )

    if not employee:
        frappe.throw("No active Employee is linked with this User.")

    today = frappe.utils.today()

    timesheet_rows = frappe.db.get_all(
        "Timesheet",
        filters={"employee": employee.name, "start_date": today, "docstatus": 0},
        fields=["name"],
        order_by="creation desc",
        limit_page_length=1,
    )

    if not timesheet_rows:
        frappe.throw("No active Timesheet was found for today.")

    timesheet = frappe.get_doc("Timesheet", timesheet_rows[0].name)

    open_row = None

    for row in timesheet.time_logs:
        if not row.completed and row.from_time and not row.to_time:
            open_row = row
            break

    if not open_row:
        frappe.throw("No work session is currently running.")

    if expected_task and open_row.task != expected_task:
        frappe.throw(
            "Another task is currently running. Open that task and stop it first."
        )

    now = frappe.utils.now_datetime()

    # Close only the current running row.
    # Do not create another row here.
    open_row.to_time = now
    open_row.completed = 1

    timesheet.save()

    return {
        "success": True,
        "timesheet": timesheet.name,
        "closed_row": open_row.name,
        "project": open_row.project or "",
        "task": open_row.task or "",
        "stopped_at": now,
    }


@frappe.whitelist()
def employee_portal_create_task():
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    subject = frappe.form_dict.get("subject") or ""
    project = frappe.form_dict.get("project") or ""
    task_type = frappe.form_dict.get("task_type") or ""

    if not subject:
        frappe.throw("Please enter Task Title.")

    # ---------------------------------------------------------
    # Project permission validation
    # ---------------------------------------------------------

    if project:
        project_rows = frappe.db.get_list(
            "Project", filters={"name": project}, fields=["name"], limit_page_length=1
        )

        if not project_rows:
            frappe.throw("Project does not exist or you do not have permission.")

    # ---------------------------------------------------------
    # Task Type permission validation
    # ---------------------------------------------------------

    if task_type:
        task_type_rows = frappe.db.get_list(
            "Task Type",
            filters={"name": task_type},
            fields=["name"],
            limit_page_length=1,
        )

        if not task_type_rows:
            frappe.throw("Task Type does not exist or you do not have permission.")

    # ---------------------------------------------------------
    # Verify custom Task Owner field
    # ---------------------------------------------------------

    task_owner_field = "custom_task_owner"

    task_meta = frappe.get_meta("Task")

    if not task_meta.has_field(task_owner_field):
        frappe.throw(
            "Task field custom_task_owner was not found. "
            "Please verify its exact fieldname."
        )

    # ---------------------------------------------------------
    # Create Task
    # ---------------------------------------------------------

    task_doc = frappe.get_doc(
        {
            "doctype": "Task",
            "subject": subject,
            "project": project or None,
            # Standard Task field is `type`.
            "type": task_type or None,
            "status": "Open",
            "is_group": 0,
            # Custom permission-query field
            "custom_task_owner": user,
        }
    )

    task_doc.insert()

    frappe.response["message"] = {
        "success": True,
        "task": task_doc.name,
        "subject": task_doc.subject,
        "project": task_doc.project,
    }


@frappe.whitelist()
def employee_portal_get_attendance_history():
    # API Method:
    # employee_portal_get_attendance_history

    # ---------------------------------------------------------
    # Logged-in User
    # ---------------------------------------------------------

    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Please login to continue.")

    # ---------------------------------------------------------
    # Logged-in Employee
    #
    # Employee client request se nahi liya jayega.
    # Logged-in User se hi resolve hoga.
    # ---------------------------------------------------------

    employee = frappe.db.get_value(
        "Employee",
        {"user_id": user, "status": "Active"},
        ["name", "employee_name", "company", "department"],
        as_dict=True,
    )

    if not employee:
        frappe.throw("Active Employee is not linked with logged-in User.")

    # ---------------------------------------------------------
    # Date Filters
    #
    # Default:
    # Current month first date to today.
    # ---------------------------------------------------------

    today = frappe.utils.getdate(frappe.utils.today())

    from_date_value = frappe.form_dict.get("from_date") or frappe.utils.get_first_day(
        today
    )

    to_date_value = frappe.form_dict.get("to_date") or today

    from_date = frappe.utils.getdate(from_date_value)

    to_date = frappe.utils.getdate(to_date_value)

    if from_date > to_date:
        frappe.throw("From Date cannot be greater than To Date.")

    # ---------------------------------------------------------
    # Summary Request
    #
    # Filter apply:
    # include_summary = 1
    #
    # Pagination:
    # include_summary = 0
    #
    # Frontend previous summary preserve karega.
    # ---------------------------------------------------------

    include_summary = frappe.utils.cint(frappe.form_dict.get("include_summary") or 0)

    summary_data = None

    # ---------------------------------------------------------
    # Server-side Pagination
    # ---------------------------------------------------------

    page_size = 10

    page = frappe.utils.cint(frappe.form_dict.get("page") or 1)

    if page < 1:
        page = 1

    # Total calendar dates in selected range.
    #
    # Example:
    # 01 June to 30 June = 30 records.
    #
    # Isliye absent/not-marked dates bhi table mein
    # calendar row ke roop mein show hongi.

    total_records = frappe.utils.date_diff(to_date, from_date) + 1

    total_pages = (total_records + page_size - 1) // page_size

    if total_pages < 1:
        total_pages = 1

    if page > total_pages:
        page = total_pages

    # ---------------------------------------------------------
    # Current Page Date Range
    #
    # Latest dates first.
    #
    # Page 1:
    # latest 10 dates
    #
    # Page 2:
    # previous 10 dates
    # ---------------------------------------------------------

    start_index = (page - 1) * page_size

    remaining_records = total_records - start_index

    page_record_count = min(page_size, remaining_records)

    page_to_date = frappe.utils.add_days(to_date, -start_index)

    page_from_date = frappe.utils.add_days(page_to_date, -(page_record_count - 1))

    today_key = str(today)

    # ---------------------------------------------------------
    # Attendance Row Helper
    #
    # Attendance is the final source of truth.
    #
    # Work:
    # Attendance.working_hours
    #
    # Break:
    # Attendance.custom_total_break_seconds
    #
    # Break Count:
    # Attendance.custom_break_count
    # ---------------------------------------------------------

    def build_attendance_row(attendance, date_key):
        # -----------------------------------------------------
        # No submitted Attendance on this date
        # -----------------------------------------------------

        if not attendance:
            return {
                "attendance": None,
                "attendance_status": "",
                "portal_status": "No Activity",
                "entry_time": None,
                "exit_time": None,
                "work_seconds": 0,
                "break_seconds": 0,
                "break_count": 0,
                "checkin_count": 0,
                "shift": "",
                "late_entry": 0,
                "early_exit": 0,
                "is_incomplete": 0,
                "has_activity": 0,
                "is_worked_day": 0,
            }

        # -----------------------------------------------------
        # Work Time
        #
        # working_hours is decimal hours.
        #
        # Example:
        # 8.5 hours = 30600 seconds
        # -----------------------------------------------------

        working_hours = frappe.utils.flt(attendance.get("working_hours") or 0)

        work_seconds = int(round(working_hours * 3600))

        if work_seconds < 0:
            work_seconds = 0

        # -----------------------------------------------------
        # Break Time
        #
        # Exact seconds saved by Before Submit script.
        # -----------------------------------------------------

        break_seconds = frappe.utils.cint(
            attendance.get("custom_total_break_seconds") or 0
        )

        if break_seconds < 0:
            break_seconds = 0

        # -----------------------------------------------------
        # Break Count
        # -----------------------------------------------------

        break_count = frappe.utils.cint(attendance.get("custom_break_count") or 0)

        if break_count < 0:
            break_count = 0

        # -----------------------------------------------------
        # Attendance Values
        # -----------------------------------------------------

        entry_time = attendance.get("in_time")

        exit_time = attendance.get("out_time")

        attendance_status = attendance.get("status") or ""

        shift = attendance.get("shift") or ""

        late_entry = frappe.utils.cint(attendance.get("late_entry") or 0)

        early_exit = frappe.utils.cint(attendance.get("early_exit") or 0)

        # -----------------------------------------------------
        # Portal Work Status
        #
        # Since submitted Attendance final source hai,
        # completed work record ko Day Ended show karenge.
        # -----------------------------------------------------

        portal_status = "No Activity"
        is_incomplete = 0

        if entry_time and exit_time:
            portal_status = "Day Ended"

        elif work_seconds > 0:
            # Imported/adjusted Attendance may have
            # working hours even when in/out are unavailable.
            portal_status = "Day Ended"

        elif entry_time and not exit_time:
            if date_key == today_key:
                portal_status = "Day Started"
            else:
                portal_status = "Incomplete"
                is_incomplete = 1

        # -----------------------------------------------------
        # Worked Day
        #
        # Attendance document existence alone is not enough.
        #
        # Absent / Leave with 0 working hours:
        # not counted.
        # -----------------------------------------------------

        is_worked_day = 1 if work_seconds > 0 else 0

        return {
            "attendance": attendance.get("name"),
            "attendance_status": (attendance_status),
            "portal_status": portal_status,
            "entry_time": entry_time,
            "exit_time": exit_time,
            "work_seconds": work_seconds,
            "break_seconds": break_seconds,
            "break_count": break_count,
            # Checkins are intentionally not queried.
            "checkin_count": 0,
            "shift": shift,
            "late_entry": (1 if late_entry else 0),
            "early_exit": (1 if early_exit else 0),
            "is_incomplete": is_incomplete,
            # Attendance exists, even if status is Absent.
            "has_activity": 1,
            "is_worked_day": (is_worked_day),
        }

    # =========================================================
    # Complete Selected Filter Summary
    #
    # This query runs only when:
    # include_summary = 1
    #
    # Next/Previous page requests skip this section.
    # =========================================================

    if include_summary:
        summary_worked_days = 0

        summary_total_work_seconds = 0
        summary_total_break_seconds = 0

        # -----------------------------------------------------
        # Load submitted Attendance records in batches
        #
        # One employee generally has maximum one Attendance
        # per calendar date, but batching keeps long ranges safe.
        # -----------------------------------------------------

        attendance_start = 0
        attendance_batch_size = 500

        while True:
            attendance_batch = frappe.db.get_all(
                "Attendance",
                filters={
                    "employee": employee.name,
                    "attendance_date": ["between", [from_date, to_date]],
                    # Final submitted Attendance only.
                    "docstatus": 1,
                },
                fields=[
                    "name",
                    "attendance_date",
                    "status",
                    "working_hours",
                    "custom_total_break_seconds",
                    "custom_break_count",
                ],
                order_by=("attendance_date asc, " "modified asc"),
                limit_start=attendance_start,
                limit_page_length=(attendance_batch_size),
            )

            # -------------------------------------------------
            # Add values into complete filter totals
            # -------------------------------------------------

            for attendance_row in attendance_batch:
                work_seconds = int(
                    round(frappe.utils.flt(attendance_row.working_hours or 0) * 3600)
                )

                if work_seconds < 0:
                    work_seconds = 0

                break_seconds = frappe.utils.cint(
                    attendance_row.get("custom_total_break_seconds") or 0
                )

                if break_seconds < 0:
                    break_seconds = 0

                summary_total_work_seconds = summary_total_work_seconds + work_seconds

                summary_total_break_seconds = (
                    summary_total_break_seconds + break_seconds
                )

                # Worked Day only when effective
                # Attendance working hours are greater than 0.

                if work_seconds > 0:
                    summary_worked_days = summary_worked_days + 1

            if len(attendance_batch) < attendance_batch_size:
                break

            attendance_start = attendance_start + attendance_batch_size

        # -----------------------------------------------------
        # Average Work Per Worked Day
        # -----------------------------------------------------

        summary_average_work_seconds = 0

        if summary_worked_days > 0:
            summary_average_work_seconds = (
                summary_total_work_seconds / summary_worked_days
            )

        # -----------------------------------------------------
        # Complete Filter Summary Response
        # -----------------------------------------------------

        summary_data = {
            "scope": "filter",
            "days_in_range": (total_records),
            "worked_days": (summary_worked_days),
            "total_work_seconds": (summary_total_work_seconds),
            "total_break_seconds": (summary_total_break_seconds),
            "average_work_seconds": (summary_average_work_seconds),
        }

    # =========================================================
    # Current Page Attendance Records
    #
    # Only current 10-date page is fetched.
    # =========================================================

    page_attendance_rows = frappe.db.get_all(
        "Attendance",
        filters={
            "employee": employee.name,
            "attendance_date": ["between", [page_from_date, page_to_date]],
            # Final submitted Attendance only.
            "docstatus": 1,
        },
        fields=[
            "name",
            "attendance_date",
            "status",
            "working_hours",
            "shift",
            "in_time",
            "out_time",
            "late_entry",
            "early_exit",
            "custom_total_break_seconds",
            "custom_break_count",
        ],
        order_by=("attendance_date asc, " "modified asc"),
        limit_page_length=100,
    )

    # ---------------------------------------------------------
    # Page Attendance Map
    # ---------------------------------------------------------

    attendance_by_date = {}

    for attendance_row in page_attendance_rows:
        attendance_date_key = str(attendance_row.attendance_date)

        attendance_by_date[attendance_date_key] = attendance_row

    # ---------------------------------------------------------
    # Build Current Page Rows
    #
    # Calendar dates latest first.
    # ---------------------------------------------------------

    history_rows = []

    for day_offset in range(0, page_record_count):
        current_date = frappe.utils.add_days(page_to_date, -day_offset)

        date_key = str(current_date)

        attendance = attendance_by_date.get(date_key)

        day_result = build_attendance_row(attendance, date_key)

        history_rows.append(
            {
                "date": date_key,
                "attendance": (day_result["attendance"]),
                "attendance_status": (day_result["attendance_status"]),
                "portal_status": (day_result["portal_status"]),
                "entry_time": (day_result["entry_time"]),
                "exit_time": (day_result["exit_time"]),
                "work_seconds": (day_result["work_seconds"]),
                "break_seconds": (day_result["break_seconds"]),
                "break_count": (day_result["break_count"]),
                "checkin_count": (day_result["checkin_count"]),
                "shift": (day_result["shift"]),
                "late_entry": (day_result["late_entry"]),
                "early_exit": (day_result["early_exit"]),
                "is_incomplete": (day_result["is_incomplete"]),
                "has_activity": (day_result["has_activity"]),
                "is_worked_day": (day_result["is_worked_day"]),
            }
        )

    # ---------------------------------------------------------
    # Pagination Record Positions
    # ---------------------------------------------------------

    from_record = start_index + 1

    to_record = start_index + page_record_count

    # ---------------------------------------------------------
    # Final Response
    # ---------------------------------------------------------

    frappe.response["message"] = {
        "employee": {
            "name": employee.name,
            "employee_name": (employee.employee_name),
            "company": employee.company,
            "department": (employee.department),
        },
        "filters": {"from_date": str(from_date), "to_date": str(to_date)},
        # Full filter summary only when
        # include_summary = 1.
        #
        # Pagination call returns None.
        # Frontend previous summary preserve karega.
        "summary": summary_data,
        "pagination": {
            "current_page": page,
            "page_size": page_size,
            "total_records": (total_records),
            "total_pages": (total_pages),
            "from_record": (from_record),
            "to_record": (to_record),
            "has_previous": (1 if page > 1 else 0),
            "has_next": (1 if page < total_pages else 0),
        },
        "rows": history_rows,
    }

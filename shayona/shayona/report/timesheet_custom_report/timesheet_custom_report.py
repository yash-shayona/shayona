# Copyright (c) 2025, Shayona Developer and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import format_time


def execute(filters: dict | None = None):
    """Return columns and data for the report.

    This is the main entry point for the report. It accepts the filters as a
    dictionary and should return columns and data. It is called by the framework
    every time the report is refreshed or a filter is updated.
    """
    columns = get_columns()
    filters = filters
    conditions = get_conditions(filters)
    filters = {**filters, **conditions}
    data = get_data(filters)

    return columns, data


def get_columns() -> list[dict]:
    """Return columns for the report.

    One field definition per column, just like a DocType field definition.
    """
    return [
        {
            "label": _("Timesheet"),
            "fieldname": "name",
            "fieldtype": "Link",
            "options": "Timesheet",
        },
        {
            "label": _("Employee"),
            "fieldname": "employee",
            "fieldtype": "Link",
            "options": "Employee",
        },
        {
            "label": _("Employee Name"),
            "fieldname": "employee_name",
            "fieldtype": "Data",
        },
        {
            "label": _("Start Date"),
            "fieldname": "start_date",
            "fieldtype": "Date",
        },
        {
            "label": _("End Date"),
            "fieldname": "end_date",
            "fieldtype": "Date",
        },
        {
            "label": _("Day"),
            "fieldname": "custom_day",
            "fieldtype": "Data",
        },
        {
            "label": _("Entry Time"),
            "fieldname": "entry_time",
            "fieldtype": "Data",
        },
        {
            "label": _("Exit Time"),
            "fieldname": "exit_time",
            "fieldtype": "Data",
        },
        {
            "label": _("Total Hours"),
            "fieldname": "total_hours",
            "fieldtype": "Float",
        },
        {
            "label": _("Total Break Hours"),
            "fieldname": "custom_total_break_hours",
            "fieldtype": "Float",
        },
        {
            "label": _("Total Effective Hours"),
            "fieldname": "custom_total_effective_hours",
            "fieldtype": "Float",
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
        },
        {
            "label": _("Auto Submit"),
            "fieldname": "custom_auto_submit",
            "fieldtype": "Data",
        },
    ]


def get_data(filters) -> list[list]:
    """Return data for the report.

    The report data is a list of rows, with each row being a list of cell values.
    """

    data = []

    timesheet = frappe.get_all(
        "Timesheet",
        filters=filters,
        fields=[
            "name",
            "employee",
            "employee_name",
            "start_date",
            "end_date",
            "custom_day",
            "total_hours",
            "custom_total_break_hours",
			"custom_total_effective_hours",
            "status",
            "custom_auto_submit",
        ],
        order_by="name desc",
    )

    for ts in timesheet:
        logs = frappe.get_all(
            "Timesheet Detail",
            filters={"parent": ts.name},
            fields=["from_time", "to_time"],
            order_by="from_time asc",
        )

        if logs:
            entry_dt = logs[0].from_time  # full datetime
            exit_dt = logs[-1].to_time  # full datetime

            entry_time = (
                format_time(entry_dt, format_string="hh:mm:ss a") if entry_dt else None
            )
            exit_time = (
                format_time(exit_dt, format_string="hh:mm:ss a") if exit_dt else None
            )
        else:
            entry_time = exit_time = None

        data.append(
            [
                ts.name,
                ts.employee,
                ts.employee_name,
                ts.start_date,
                ts.end_date,
                ts.custom_day,
                entry_time,
                exit_time,
                ts.total_hours,
                ts.custom_total_break_hours,
                ts.custom_total_effective_hours,
                ts.status,
                ts.custom_auto_submit,
            ]
        )

    return data


def get_conditions(filters):
    conditions = {}

    if filters.get("start_date"):
        # start_date = getdate(filters.get("start_date"))
        conditions["start_date"] = [">=", filters.get("start_date")]

    if filters.get("end_date"):
        # end_date = getdate(filters.get("end_date"))
        conditions["end_date"] = ["<=", filters.get("end_date")]

    return conditions

# Copyright (c) 2026, Yash Solanki and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
    """Return columns and data for the report.

    This is the main entry point for the report. It accepts the filters as a
    dictionary and should return columns and data. It is called by the framework
    every time the report is refreshed or a filter is updated.
    """
    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns() -> list[dict]:
    """Return columns for the report.

    One field definition per column, just like a DocType field definition.
    """
    return [
        {"label": "Date", "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": "Cups", "fieldname": "no_of_cups", "fieldtype": "Int", "width": 100},
        {
            "label": "Rate",
            "fieldname": "rate_per_cup",
            "fieldtype": "Currency",
            "width": 100,
        },
        {
            "label": "Amount",
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 120,
        },
    ]


def get_data(filters: dict) -> list[list]:
    """Return data for the report.

    The report data is a list of rows, with each row being a list of cell values.
    """
    conditions = ""

    if filters.get("month"):
        conditions += f" AND DATE_FORMAT(date, '%Y-%m') = '{filters.get('month')}'"
        
    data = frappe.db.sql(
        f"""
		SELECT 
			date,
			no_of_cups,
			rate_per_cup,
			total_amount
		FROM `tabTea Entry`
		WHERE 1=1 {conditions}
		ORDER BY date ASC
	""",
        as_dict=True,
    )
    return data

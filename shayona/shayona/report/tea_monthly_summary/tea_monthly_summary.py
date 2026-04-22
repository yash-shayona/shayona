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
        {
            "label": "Month", 
            "fieldname": "month", 
            "fieldtype": "Data", 
            "width": 120
        },
        {
            "label": "Total Cups",
            "fieldname": "total_cups",
            "fieldtype": "Int",
            "width": 120,
        },
        {
            "label": "Total Amount",
            "fieldname": "total_amount",
            "fieldtype": "Currency",
            "width": 150,
        },
    ]


def get_data(filters: dict) -> list[list]:
    """Return data for the report.

    The report data is a list of rows, with each row being a list of cell values.
    """
    conditions = ""

    if filters.get("from_date"):
        conditions += f" AND date >= '{filters.get('from_date')}'"
    if filters.get("to_date"):
        conditions += f" AND date <= '{filters.get('to_date')}'"

    data = frappe.db.sql(
        f"""
		SELECT 
			DATE_FORMAT(date, '%b-%Y') as month,
			SUM(no_of_cups) as total_cups,
			SUM(total_amount) as total_amount
		FROM `tabTea Entry`
		WHERE 1=1 {conditions}
		GROUP BY month
		ORDER BY month DESC
	""",
        as_dict=True,
    )

    return data

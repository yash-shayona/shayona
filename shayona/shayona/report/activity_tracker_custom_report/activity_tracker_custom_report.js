// Copyright (c) 2025, Yash Solanki and contributors
// For license information, please see license.txt

frappe.query_reports["Activity Tracker Custom Report"] = {
	"filters": [
		{
			"fieldname": "user",
			"label": "User",
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"fieldname": "employee",
			"label": "Employee",
			"fieldtype": "Link",
			"options": "Employee",
		},
		{
			"fieldname": "timesheet",
			"label": "Timesheet",
			"fieldtype": "Link",
			"options": "Timesheet",
		},
		{
			"fieldname": "date_range",
			"label": __("Date Range"),
			"fieldtype": "DateRange",
			"default": [frappe.datetime.month_start(), frappe.datetime.month_end()],
			// "reqd": 1,
		},
	]
};

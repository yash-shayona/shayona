// Copyright (c) 2025, Shayona Developer and contributors
// For license information, please see license.txt

frappe.query_reports["Timesheet Custom Report"] = {
	filters: [
		{
			"fieldname": "employee",
			"label": __("Employee"),
			"fieldtype": "Link",
			"options": "Employee",
			// "reqd": 1,
		},
		{
			"fieldname": "start_date",
			"label": __("Start Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			// "reqd": 1,
		},
		{
			"fieldname": "end_date",
			"label": __("End Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			// "reqd": 1,
		},
		{
			"fieldname": "status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nDraft\nSubmitted\nCancelled\nBilled\nPayslip",
			// "reqd": 1,
		},
	],
};

// Copyright (c) 2025, Shayona Developer and contributors
// For license information, please see license.txt

frappe.query_reports["RBS Task Report"] = {
	filters: [
		{
			"fieldname": "name",
			"label": __("Task"),
			"fieldtype": "Link",
			"options": "Task",
			// "reqd": 1,
		},
		{
			"fieldname": "task_update_date",
			"label": __("Task Date"),
			"fieldtype": "DateRange",
			"default": [frappe.datetime.month_start(), frappe.datetime.month_end()],
			// "reqd": 1,
		},
		{
			"fieldname": "task_status",
			"label": __("Status"),
			"fieldtype": "Select",
			"options": "\nIn Progress\nReceived\nCompleted\nRTS\nSample Out\nCanceled\nOn Hold",
			// "reqd": 1,
		},
	],
};

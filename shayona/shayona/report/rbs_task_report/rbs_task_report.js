// Copyright (c) 2025, Shayona Developer and contributors
// For license information, please see license.txt

frappe.query_reports["RBS Task Report"] = {
	filters: [
		{
			"fieldname": "task_update_date",
			"label": __("Task Date"),
			"fieldtype": "DateRange",
			"default": [frappe.datetime.month_start(), frappe.datetime.month_end()],
			// "reqd": 1,
		},
		{
			"fieldname": "custom_task_owner",
			"label": __("Task Owner"),
			"fieldtype": "Link",
			"options": "User",
		},
		{
			"fieldname": "name",
			"label": __("Task"),
			"fieldtype": "Link",
			"options": "Task",
			"get_query": function() {
				var custom_task_owner = frappe.query_report.get_filter_value("custom_task_owner");
				var filters = {
					"custom_project_type": "Regency"
				};
				if (custom_task_owner) {
					filters["custom_task_owner"] = custom_task_owner;
				}
				return {
					"doctype": "Task",
					"filters": filters
				}
			},
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

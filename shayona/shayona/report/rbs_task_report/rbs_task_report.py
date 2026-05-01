# Copyright (c) 2025, Shayona Developer and contributors
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
	filters = auto_split_filters(filters)
	data = get_data(filters)
 
	return columns, data


def get_columns() -> list[dict]:
	"""Return columns for the report.

	One field definition per column, just like a DocType field definition.
	"""
	return [
		{
			"label": _("Task"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Task",
		},
		{
			"label": _("Request Id"),
			"fieldname": "subject",
			"fieldtype": "Data",
		},
		{
			"label": _("Buyer Name"),
			"fieldname": "buyer_name",
			"fieldtype": "Data",
		},
		{
			"label": _("Vibe Id"),
			"fieldname": "vibe_id",
			"fieldtype": "float",
		},
		{
			"label": _("User Name"),
			"fieldname": "buyer_user_name",
			"fieldtype": "Data",
		},
		{
			"label": _("Task Type"),
			"fieldname": "project",
			"fieldtype": "Data",
		},
		{
			"label": _("Task Detail"),
			"fieldname": "description",
			"fieldtype": "Data",
		},
		{
			"label": _("Date"),
			"fieldname": "task_update_date",
			"fieldtype": "Date",
		},
		{
			"label": _("Task Status"),
			"fieldname": "status",
			"fieldtype": "Data",
		},
		{
			"label": _("Products"),
			"fieldname": "products",
			"fieldtype": "Data",
			"width": 200
		},
		{
			"label": _("Comment"),
			"fieldname": "task_detail",
			"fieldtype": "Data",
		},
		{
			"label": _("SKU"),
			"fieldname": "task_sku",
			"fieldtype": "Data",
		},
	]


def get_data(filters) -> list[list]:
	"""Return data for the report.

	The report data is a list of rows, with each row being a list of cell values.
	"""
	data = []
 
	tasks = frappe.get_all(
     "Task", 
	 fields=["name", "subject", "description", "type", "project", "custom_project_type"],
  	 filters={"status": ["!=", "Cancelled"], "custom_project_type": ["=", "Regency"], **filters["task_filters"]},
	 order_by="name desc"
	)
 
	for t in tasks:
		project = frappe.get_value("Project", t.project, "project_name")
		
		# Fetch RBS Task (one-to-one)
		rbs_task = frappe.get_all(
			"RBS Task",
			fields=["buyer_name", "vibe_id", "buyer_user_name"],
			filters={"parent": t.name, "parenttype": "Task", **filters["rbs_task_filters"]},
			limit_page_length=1
		)

		rbst = rbs_task[0] if rbs_task else {}

		# Fetch RBS Task Update (one-to-many)
		rbs_task_updates = frappe.get_all(
			"RBS Task Update",
			fields=["task_update_date", "task_detail", "task_sku", "task_status", "new_static_product", "existing_static_product", "new_apparel_product", "existing_apparel_product", "new_variable_product", "existing_variable_product", "new_category", "existing_category", "revised_product", "revised_category"],
			filters={"parent": t.name, "parenttype": "Task", **filters["rbs_task_update_filters"]},
			order_by="task_update_date desc"
		)

		# # Add one row per Task Update
		for idx, rbstu in enumerate(rbs_task_updates):
			if idx == 0:
        		# First row → show Task info
				task_name = t.name
				subject = t.subject
				buyer_name = rbst.get("buyer_name")
				vibe_id = rbst.get("vibe_id")
				buyer_user_name = rbst.get("buyer_user_name")
				project_name = project
				task_description = t.get("description")
			else:
        		# Next rows → blank
				task_name = ""
				subject = ""
				buyer_name = ""
				vibe_id = ""
				buyer_user_name = ""
				project_name = ""
				task_description = ""
    
			products = products_cell_prepare(rbstu)

			data.append([
    		    task_name,
    		    subject,
    		    buyer_name,
    		    vibe_id,
    		    buyer_user_name,
    		    project_name,
    		    task_description,
    		    rbstu.get("task_update_date"),
    		    rbstu.get("task_status"),
			    products,
    		    rbstu.get("task_detail"),
    		    rbstu.get("task_sku"),
    		])

	return data

def auto_split_filters(filters):
    task_fields = set(frappe.get_meta("Task").get_valid_columns())
    rbs_task_fields = set(frappe.get_meta("RBS Task").get_valid_columns())
    rbs_task_update_fields = set(frappe.get_meta("RBS Task Update").get_valid_columns())

    task_filters = {}
    rbs_task_filters = {}
    rbs_task_update_filters = {}
    
    if filters.get("task_update_date"):
        start_date, end_date = filters["task_update_date"]
        filters["task_update_date"] = ["between", [start_date, end_date]]

    for key, value in filters.items():
        if key in task_fields:
            task_filters[key] = value
        elif key in rbs_task_fields:
            rbs_task_filters[key] = value
        elif key in rbs_task_update_fields:
            rbs_task_update_filters[key] = value
            
    filters = {
		"task_filters": task_filters,
		"rbs_task_filters": rbs_task_filters,
		"rbs_task_update_filters": rbs_task_update_filters,
	}

    return filters

def products_cell_prepare(rbstu_row):
	products = []
 
	if rbstu_row.get("new_static_product") and rbstu_row.get("new_static_product") > 0:
		products.append("New Static: " + str(rbstu_row.get("new_static_product")))
	if rbstu_row.get("existing_static_product") and rbstu_row.get("existing_static_product") > 0:
		products.append("Existing Static: " + str(rbstu_row.get("existing_static_product")))
	if rbstu_row.get("new_apparel_product") and rbstu_row.get("new_apparel_product") > 0:
		products.append("New Apparel: " + str(rbstu_row.get("new_apparel_product")))
	if rbstu_row.get("existing_apparel_product") and rbstu_row.get("existing_apparel_product") > 0:
		products.append("Existing Apparel: " + str(rbstu_row.get("existing_apparel_product")))
	if rbstu_row.get("new_variable_product") and rbstu_row.get("new_variable_product") > 0:
		products.append("New Variable: " + str(rbstu_row.get("new_variable_product")))
	if rbstu_row.get("existing_variable_product") and rbstu_row.get("existing_variable_product") > 0:
		products.append("Existing Variable: " + str(rbstu_row.get("existing_variable_product")))
	if rbstu_row.get("new_category") and rbstu_row.get("new_category") > 0:
		products.append("New Category: " + str(rbstu_row.get("new_category")))
	if rbstu_row.get("existing_category") and rbstu_row.get("existing_category") > 0:
		products.append("Existing Category: " + str(rbstu_row.get("existing_category")))
	if rbstu_row.get("revised_product") and rbstu_row.get("revised_product") > 0:
		products.append("New Revised: " + str(rbstu_row.get("revised_product")))
	if rbstu_row.get("revised_category") and rbstu_row.get("revised_category") > 0:
		products.append("Revised Category: " + str(rbstu_row.get("revised_category")))
	products = " | ".join(products)

	return products
# Copyright (c) 2025, Shayona Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class RBSTask(Document):
	pass

@frappe.whitelist()
def get_rbs_task(name):
    return frappe.get_value(
        "RBS Task",
        filters={"name": name},
        fieldname="*",
        as_dict=True
    )
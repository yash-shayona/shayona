# Copyright (c) 2025, Shayona Developer and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class TaskChecklist(Document):
	pass

@frappe.whitelist()
def get_task_checklist(task):
    return frappe.get_all(
        "Task Checklist",
        filters={"parent": task},
        fields=["item", "done"]
    )
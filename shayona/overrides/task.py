import frappe
from frappe.utils import get_datetime

def validate(doc, method):
    check_custom_rbs_task_update_date(doc)

def before_insert(doc, method):
    # Get today's date once
    today = get_datetime().date()
    
    if not doc.get("custom_rbs_task"):
        doc.append("custom_rbs_task", {
            "task_date": today
        })
    
    if not doc.get("custom_rbs_task_update") or len(doc.custom_rbs_task_update) == 0:
        doc.append("custom_rbs_task_update", {
            "task_update_date": today,
            "task_status": "Received"
        })

    # If exactly 1 row
    if len(doc.custom_rbs_task_update) == 1:
        row = doc.custom_rbs_task_update[0]

        if not row.task_update_date or not row.task_status:
            row.task_update_date = today
            row.task_status = "Received"
    
def before_save(doc, method):
    if not doc.get("custom_rbs_task_update") or len(doc.custom_rbs_task_update) == 0:
        doc.append("custom_rbs_task_update", {
            "task_update_date": get_datetime().date(),
            "task_status": "Received"
        })
        
def check_custom_rbs_task_update_date(doc):
    if doc.custom_rbs_task_update:
        for row in doc.custom_rbs_task_update:
            if row.task_update_date < doc.custom_rbs_task[0].task_date:
                frappe.throw("Task Update Date cannot be before Task Date")
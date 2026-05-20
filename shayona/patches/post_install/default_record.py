import frappe

def execute():
    # add new activity type "Break"
    if not frappe.db.exists('Activity Type', 'Break'):
        document = frappe.new_doc('Activity Type')
        document.activity_type = 'Break'
        document.disabled = 0
        document.insert()

    frappe.db.commit()
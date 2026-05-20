import frappe


def setup_default_data():
    print("Setting up default data...")

    activity_type()

    frappe.db.commit()


def activity_type():
    # add new activity type "Break"
    if not frappe.db.exists("Activity Type", "Break"):
        document = frappe.new_doc("Activity Type")
        document.activity_type = "Break"
        document.disabled = 0
        document.insert()

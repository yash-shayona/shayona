import frappe

PATCHES = [
    "default_record"
]

def execute_patches():
    print("Executing patches...")

    try:
        frappe.flags.in_patch = True

        for patch in PATCHES:
            frappe.get_attr(f"shayona.patches.post_install.{patch}.execute")()
    finally:
        frappe.flags.in_patch = False
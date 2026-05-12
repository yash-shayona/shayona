import frappe

ALLOWED_ROLES = [
    "System Manager", 
    "Projects Manager",
    "Projects User"
]


def get_permission_query_conditions(user):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return None

    user_roles = frappe.get_roles(user)
    if any(role in ALLOWED_ROLES for role in user_roles):
        return None

    return """(
        `tabTask`.owner = '{user}' or 
        `tabTask`.custom_task_owner = '{user}'
    )""".format(user=user)


def has_permission(doc, user):
    if not user:
        user = frappe.session.user

    if user == "Administrator":
        return True

    user_roles = frappe.get_roles(user)
    if any(role in ALLOWED_ROLES for role in user_roles):
        return True

    if doc.owner == user or doc.custom_task_owner == user:
        return True

    return False

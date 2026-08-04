import frappe

# These standard ERPNext roles can access the Project Portal.
PROJECT_PORTAL_ALLOWED_ROLES = frozenset(
    {
        "Employee",
        "Projects User",
        "Projects Manager",
    }
)

# These administrative roles bypass the portal-specific role requirement.
PROJECT_PORTAL_BYPASS_ROLES = frozenset({"System Manager"})


def require_project_portal_access(user=None):
    # This applies the same server-side role rule to portal pages and their APIs.
    user = user or frappe.session.user

    if user == "Administrator":
        return

    user_roles = set(frappe.get_roles(user))

    if user_roles & PROJECT_PORTAL_BYPASS_ROLES:
        return

    if user_roles & PROJECT_PORTAL_ALLOWED_ROLES:
        return

    frappe.throw(
        "You do not have permission to access Project Portal.",
        frappe.PermissionError,
    )

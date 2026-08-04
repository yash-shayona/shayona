import frappe

from shayona.permissions.project_portal import require_project_portal_access


def get_context(context):
    # This configures the Project Portal My Tasks child route.
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/shayona/projects/my-tasks"
        )
        raise frappe.Redirect

    # This verifies the logged-in user has a Project Portal role before rendering.
    require_project_portal_access()

    context.no_cache = 1
    context.show_sidebar = 0
    context.sidebar_columns = 2
    context.no_header = 1
    context.no_breadcrumbs = 1
    context.full_width = 1
    context.portal_page = "my-tasks"
    context.portal_title = "My Tasks"

import frappe

from shayona.permissions.project_portal import require_project_portal_access


def get_context(context):
    # This receives the Project name from Frappe's app-level dynamic website route.
    project_name = frappe.utils.cstr(
        frappe.form_dict.get("project_name") or ""
    ).strip()

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to={0}".format(frappe.local.request.path)
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
    context.portal_page = "workspace"
    context.project_name = project_name
    context.portal_title = "Project Workspace"

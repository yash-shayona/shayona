import frappe


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = (
            "/login?redirect-to=/shayona/employee/attendance"
        )
        raise frappe.Redirect

    context.no_cache = 1

    context.show_sidebar = 1
    # context.sidebar_title = "Employee Portal"
    context.sidebar_columns = 2

    context.no_header = 1
    context.no_breadcrumbs = 1
    context.full_width = 1
    context.title = "Attendance History"

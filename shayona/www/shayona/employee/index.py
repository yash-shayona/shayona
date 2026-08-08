import frappe


def get_context(context):
    # This keeps the portal behind Frappe login so we can reuse the current user session safely.
    # if frappe.session.user == "Guest":
    #     frappe.local.flags.redirect_location = "/login?redirect-to=/shayona/employee"
    #     raise frappe.Redirect

    # context.no_cache = 1
    # context.show_sidebar = False
    # context.no_header = 1
    # context.no_breadcrumbs = 1
    # context.full_width = 1
    # context.title = "Employee Work Portal"

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/shayona/employee"
        raise frappe.Redirect

    context.no_cache = 1

    # Built-in Website Sidebar
    context.show_sidebar = 0
    # context.sidebar_title = "Employee Portal"
    context.sidebar_columns = 2

    context.no_header = 1
    context.no_breadcrumbs = 1
    context.full_width = 1
    context.title = "Employee Work Portal"

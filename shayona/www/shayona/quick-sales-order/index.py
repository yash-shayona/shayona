import frappe
from frappe import _
from frappe.utils import get_fullname, nowdate


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = (
			"/login?redirect-to=/shayona/quick-sales-order"
		)
		raise frappe.Redirect

	if not frappe.has_permission("Sales Order", "create"):
		frappe.throw(
			_("You do not have permission to create a Sales Order."),
			frappe.PermissionError,
		)

	context.no_cache = 1
	context.show_sidebar = 0
	context.no_header = 1
	context.no_breadcrumbs = 1
	context.full_width = 1
	context.title = _("Quick Sales Order")
	context.transaction_date = nowdate()
	context.user_fullname = get_fullname(frappe.session.user)

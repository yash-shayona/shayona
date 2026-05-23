# Copyright (c) 2025, Yash Solanki and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, nowdate


class ActivityTracker(Document):
	pass
 
def delete_old_activity_trackers():
    """
    Delete Activity Tracker records older than configured days
    """

    # Read retention days from config (default 30 days)
    retention_days = frappe.get_site_config().get(
        "activity_tracker_retention_days", 30
    )

    cutoff_date = add_days(nowdate(), -int(retention_days))

    old_trackers = frappe.get_all(
        "Activity Tracker",
        filters={"date": ("<", cutoff_date)},
        pluck="name"
    )

    for tracker_name in old_trackers:
        try:
            # This automatically deletes:
            # - child table rows
            # - attached files (Files linked via File doctype)
            frappe.delete_doc(
                "Activity Tracker",
                tracker_name,
                force=1,
                ignore_permissions=True
            )
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Failed deleting Activity Tracker {tracker_name}"
            )

    frappe.db.commit()
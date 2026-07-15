import frappe
from erpnext.projects.doctype.timesheet.timesheet import Timesheet


class CustomTimesheet(Timesheet):
    pass

def validate(doc, method):
    doc.check_timesheet_exists()
    doc.check_employee_set_or_not()
    # doc.allow_timer_start_end()


def before_insert(doc, method):
    doc.set_timesheet_day()
    doc.set_company()


def before_save(doc, method):
    # doc.calculate_total_break_hours()
    pass


def before_submit(doc, method):
    doc.set_auto_submit_flag()
    doc.calculate_break_adjustment()

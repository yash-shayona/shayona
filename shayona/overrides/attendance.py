import frappe


def before_submit(doc, method):
    doc.attendance_effective_hours_calculate()

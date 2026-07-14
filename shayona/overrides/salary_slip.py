import frappe


def before_validate(doc, method):
    doc.attendance_hour_based_salary()

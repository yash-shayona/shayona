import frappe


def validate(doc, method):
    doc.check_duplicate_subject()
    doc.check_custom_rbs_task_update_date()
    doc.validate_on_completed()


def before_insert(doc, method):
    pass


def before_save(doc, method):
    doc.set_default_rbs_task_row()
    doc.set_default_rbs_task_update_row()
    doc.handle_status_change_to_update_table()

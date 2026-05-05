frappe.ui.form.on("Timesheet", {
    setup: function (frm) {
        restrict_time_log_row_modification(frm);
    },

    onload: function (frm) {
        restrict_time_log_row_modification(frm);
    },

    refresh(frm) {
        restrict_time_log_row_modification(frm);
    },

    validate: function (frm) {
        check_employee_selected_or_not(frm);
    }
});

function restrict_time_log_row_modification(frm) {
    if (frappe.session.user === "Administrator") {
        return;
    }

    const allowed_roles = [
        "System Manager",
        "Project Manager",
        "HR Manager"
    ];

    const user_roles = frappe.user_roles || [];

    const has_access = user_roles.some(role => allowed_roles.includes(role));

    if (has_access) return;

    frm.set_df_property("time_logs", "cannot_add_rows", true);
    frm.set_df_property("time_logs", "cannot_delete_rows", true);
    frm.set_df_property("time_logs", "read_only", true);
}

function check_employee_selected_or_not(frm) {
    if (!frm.doc.employee) {
        // frappe.msgprint(__("Employee must be selected."));

        // Add Frappe "error" highlight
        frm.fields_dict.employee.$wrapper.addClass('has-error highlight');

        // defer focus so the DOM is ready
        setTimeout(() => {
            frm.fields_dict.employee.$wrapper.find('input').focus();
        }, 100);

        setTimeout(() => {
            frm.fields_dict.employee.$wrapper.removeClass('highlight');
        }, 1500);

        frappe.validated = false;
    }
}
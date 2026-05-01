frappe.ui.form.on("Timesheet", {
    refresh(frm) {
        manually_timesheet_detail_add_rows(frm);
    },

    onload: function (frm) {

    },

    validate: function (frm) {
        // check_employee_selected_or_not(frm);
    }
});

function manually_timesheet_detail_add_rows(frm) {
    // allowed roles who can manually add rows
    const allowed_roles = ["System Manager", "HR Manager", "Administrator"];

    let has_access = allowed_roles.some(role => frappe.user_roles.includes(role));

    // child table grid
    let grid = frm.get_field("time_logs").grid;

    if (!has_access) {
        console.log(grid);

        // disable add row
        grid.cannot_add_rows = true;

        // Hide delete icon in toolbar
        grid.wrapper.find('.grid-remove-rows').hide();

        // Hide duplicate row button
        grid.wrapper.find('.grid-duplicate-row').hide();

        frm.refresh_field("time_logs");
    }
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
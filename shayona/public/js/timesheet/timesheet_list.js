frappe.listview_settings['Timesheet'] = {
    onload: function (listview) {
        if (frappe.session.user === "Administrator") {
            return;
        }

        if (frappe.user.has_role("Employee")) {
            // Wait 200ms so that the dropdown menu is created
            setTimeout(() => {
                // Hide Report View item
                const report_item = $(`li[data-view="Report"]`);
                // const li = document.querySelector(`li[data-view="Report"]`);
                
                if (report_item.length) report_item.remove();
            }, 200);
        }
    }
};
frappe.listview_settings['Task'] = {
    onload: function (listview) {

    },

    get_indicator: function (doc) {
        var colors = {
            "Open": "orange",
            "Overdue": "red",
            "Pending Review": "orange",
            "Working": "orange",
            "Completed": "green",
            "Cancelled": "dark grey",
            "Template": "blue",
            "RTS Info Needed": "blue",
            "Revisions Needed": "blue",
        };
        return [__(doc.status), colors[doc.status], "status,=," + doc.status];
    }
};
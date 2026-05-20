frappe.require("/assets/erpnext/js/projects/timer.js", function () {
    erpnext.timesheet.timer = function (frm, row, timestamp = 0) {
        let dialog = new frappe.ui.Dialog({
            title: __("Timer"),
            fields: [
                {
                    fieldtype: "Link",
                    label: __("Activity Type"),
                    fieldname: "activity_type",
                    reqd: 1,
                    options: "Activity Type",
                },
                {
                    fieldtype: "Link",
                    label: __("Project"),
                    fieldname: "project",
                    options: "Project",
                    onchange: function () {
                        dialog.set_value("task", "");
                        dialog.fields_dict.task.refresh();
                    }
                },
                {
                    fieldtype: "Link",
                    label: __("Task"),
                    fieldname: "task",
                    options: "Task",
                    get_query: function () {
                        let project = dialog.get_value("project");

                        let filters = [
                            ["Task", "status", "not in", ["Cancelled", "Completed"]],
                            ["Task", "is_group", "=", 0],
                        ];

                        if (project) {
                            filters.push(["Task", "project", "=", project]);
                        }

                        return { filters };
                    },
                },
                {
                    fieldtype: "Float",
                    label: __("Expected Hrs"),
                    fieldname: "expected_hours"
                },
                { fieldtype: "Section Break" },
                { fieldtype: "HTML", fieldname: "timer_html" },
            ],
        });

        if (row) {
            dialog.set_values({
                activity_type: row.activity_type,
                project: row.project,
                task: row.task,
                expected_hours: row.expected_hours,
            });
        } else {
            dialog.set_values({
                project: frm.doc.parent_project,
            });
        }

        dialog.get_field("timer_html").$wrapper.append(`
            <div class="stopwatch">
                <span class="hours">00</span>
                <span class="colon">:</span>
                <span class="minutes">00</span>
                <span class="colon">:</span>
                <span class="seconds">00</span>
            </div>
            <div class="playpause text-center">
                <button class="btn btn-primary btn-start"> ${__("Start")} </button>
                <button class="btn btn-primary btn-complete"> ${__("Complete")} </button>
            </div>
        `);

        erpnext.timesheet.control_timer(frm, dialog, row, timestamp);
        dialog.show();
    };
});
frappe.ui.form.on("Task", {
    setup: function (frm) {
        restrict_rbs_task_row_modification(frm);
    },

    onload: function (frm) {
        restrict_rbs_task_row_modification(frm);
    },

    refresh: function (frm) {
        restrict_rbs_task_row_modification(frm);
    },

    onload_post_render: function (frm) {

    },

    validate(frm) {
        check_custom_rbs_task_update_date(frm);
    },

    type(frm) {
        task_type_change(frm);
    },

    after_save(frm) {

    }
});

frappe.ui.form.on("RBS Task", {
    custom_rbs_task_add: function (frm, cdt, cdn) {
        restrict_rbs_task_row_modification(frm);
    },

    custom_rbs_task_remove: function (frm, cdt, cdn) {
        restrict_rbs_task_row_modification(frm);
    },

    vibe_id(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        if (!row.vibe_id) {
            frappe.model.set_value(cdt, cdn, "buyer_name", "");
            return;
        }

        frappe.db.get_value(
            "RBS Buyer",
            {
                "vibe_id": row.vibe_id
            },
            ["buyer_name"]
        ).then(r => {
            if (r.message.buyer_name) {
                frappe.model.set_value(cdt, cdn, "buyer_name", r.message.buyer_name);
            } else {
                frappe.msgprint("No Buyer found for Vibe ID: " + row.vibe_id);
                frappe.model.set_value(cdt, cdn, "buyer_name", "");
            }
        });
    },
});

frappe.ui.form.on("RBS Task Update", {
    refresh: function (frm) {

    }
});

function restrict_rbs_task_row_modification(frm) {
    // Skip for Administrator
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

    // If privileged user → no restriction
    if (has_access) {
        frm.set_df_property("custom_rbs_task", "cannot_add_rows", false);
        return;
    }

    let row_count = (frm.doc.custom_rbs_task || []).length;

    if (row_count >= 1) {
        frm.set_df_property("custom_rbs_task", "cannot_add_rows", true);
        frm.set_df_property("custom_rbs_task", "cannot_delete_rows", true);
    } else {
        frm.set_df_property("custom_rbs_task", "cannot_add_rows", false);
    }

    frm.refresh_field("custom_rbs_task");
}

function task_type_change(frm) {
    if (!frm.doc.type) {
        frm.clear_table("custom_task_checklist");
        frm.refresh_field("custom_task_checklist");
        return;
    }

    frappe.db.exists(
        "Checklist Template",
        frm.doc.type
    ).then(exists => {
        if (!exists) {
            return;
        }
        // STEP 1: Load template
        frappe.call({
            method: "frappe.client.get",
            args: {
                doctype: "Checklist Template",
                name: frm.doc.type
            },
            callback: function (template_res) {
                if (!template_res.message) return;

                // STEP 2: Load saved checklist first
                frappe.call({
                    method: "shayona.shayona.doctype.task_checklist.task_checklist.get_task_checklist",
                    args: { task: frm.doc.name },
                    callback: function (saved_res) {
                        let saved_list = saved_res.message || [];

                        // Clear old table
                        frm.clear_table("custom_task_checklist");

                        if (!template_res.message.items.length) return;
                        template_res.message.items.forEach(template_row => {
                            let exists = saved_list.some(s => s.item === template_row.item);
                            if (frm.doc.custom_task_checklist.length < template_res.message.items.length) {
                                let row = frm.add_child("custom_task_checklist");
                                row.item = exists ? saved_list.find(s => s.item === template_row.item).item : template_row.item;
                                row.done = exists ? saved_list.find(s => s.item === template_row.item).done : 0;
                            }
                        });
                        // Expand section
                        // frm.fields_dict.sb_checklist.collapse(false);
                        // Refresh
                        frm.refresh_field("custom_task_checklist");
                    }
                });
            },
            error: function (err) {
                frm.clear_table("custom_task_checklist");
                frm.refresh_field("custom_task_checklist");
            }
        });
    });
}

function check_custom_rbs_task_update_date(frm) {
    if (frm.doc.custom_rbs_task && frm.doc.custom_rbs_task.length) {
        if (frm.doc.custom_rbs_task_update) {
            for (let i = 0; i < frm.doc.custom_rbs_task_update.length; i++) {
                if (frm.doc.custom_rbs_task_update[i].task_update_date < frm.doc.custom_rbs_task[0].task_date) {
                    frappe.throw("Task Update Date cannot be before Task Date");
                }
            }
        }
    }
}
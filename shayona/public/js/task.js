frappe.ui.form.on("Task", {
    refresh: function (frm) {

    },

    onload: function (frm) {
        toggle_add_row_button(frm, "custom_rbs_task");
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
        toggle_add_row_button(frm, "custom_rbs_task");
    },

    custom_rbs_task_remove: function (frm, cdt, cdn) {
        toggle_add_row_button(frm, "custom_rbs_task");
    },

    vibe_id(frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        frappe.db.get_value("RBS Buyer", { "vibe_id": row.vibe_id },
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

function toggle_add_row_button(frm, ctfn) {
    setTimeout(() => {
        let table = frm.get_field(ctfn).grid;
        const child_table_field_name = ctfn;

        if (frm.doc[child_table_field_name] && frm.doc[child_table_field_name].length >= 1) {
            // Hide the add row button this is actual work
            frm.get_field(child_table_field_name).grid.cannot_add_rows = true;
            table.wrapper.find('.grid-remove-rows').hide();
            table.wrapper.find('.grid-duplicate-rows').hide();
            frm.refresh_field(child_table_field_name);
        } else {
            // this is actual work
            frm.get_field(child_table_field_name).grid.cannot_add_rows = false;
            table.wrapper.find('.grid-remove-rows').show();
            table.wrapper.find('.grid-duplicate-rows').show();
            frm.refresh_field(child_table_field_name);
        }
    }, 100);
}

function task_type_change(frm) {
    if (!frm.doc.type) {
        frm.clear_table("task_checklist");
        frm.refresh_field("task_checklist");
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
            frm.clear_table("task_checklist");
            frm.refresh_field("task_checklist");
        }
    });
}

function check_custom_rbs_task_update_date(frm) {
    if (frm.doc.custom_rbs_task_update) {
        for (let i = 0; i < frm.doc.custom_rbs_task_update.length; i++) {
            if (frm.doc.custom_rbs_task_update[i].task_update_date < frm.doc.custom_rbs_task[0].task_date) {
                frappe.throw("Task Update Date cannot be before Task Date");
            }
        }
    }
}
frappe.ui.form.on("Task", {
    refresh: function (frm) {
        // rbs_task_html_render(frm);
        // render fields only once
        // if (!frm.dynamic_fields_rendered) {
        //     rbs_task_html_render(frm);
        //     frm.dynamic_fields_rendered = true;
        // }
        // frappe.msgprint("Public Task js loaded");
    },

    onload: function (frm) {
        toggle_add_row_button(frm, "custom_rbs_task");
    },

    onload_post_render: function (frm) {
        // check_control_event_change(frm);
    },

    validate(frm) {
        // save_rbs_task_data(frm);
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
                // frappe.msgprint("No Buyer found for Vibe ID: " + row.vibe_id);
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
        const child_table_field_name = ctfn;

        if (frm.doc[child_table_field_name] && frm.doc[child_table_field_name].length >= 1) {
            // Hide the add row button this is actual work
            frm.get_field(child_table_field_name).grid.cannot_add_rows = true;
            frm.refresh_field(child_table_field_name);
        } else {
            // this is actual work
            frm.get_field(child_table_field_name).grid.cannot_add_rows = false;
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

// function rbs_task_html_render(frm) {
//     // frm.get_field("custom_rbs_task_html").$wrapper.html(`
//     //         <div class="form-group">
//     //             <label>Task Date</label>
//     //             <input type="date" class="form-control" id="task_date">
//     //         </div>
//     //         <div class="form-group">
//     //             <label>Buyer Name</label>
//     //             <input class="form-control" id="buyer_name">
//     //         </div>
//     //         <div class="form-group">
//     //             <label>Vibe ID</label>
//     //             <input class="form-control" id="vibe_id">
//     //         </div>
//     //         <div class="form-group">
//     //             <label>Buyer User Name</label>
//     //             <input class="form-control" id="buyer_user_name">
//     //         </div>
//     //     `);

//     frm.custom_controls = {};   // store references

//     const wrapper = frm.get_field("custom_rbs_task_html").$wrapper;

//     const fields = [
//         { fieldname: "task_date", fieldtype: "Date", label: "Task Date" },
//         { fieldname: "buyer_name", fieldtype: "Link", options: "RBS Buyer", label: "Buyer Name" },
//         { fieldname: "vibe_id", fieldtype: "Data", label: "Vibe ID" },
//         { fieldname: "buyer_user_name", fieldtype: "Link", options: "RBS Buyer User", label: "Buyer User Name" }
//     ];

//     fields.forEach(df => {
//         let control = frappe.ui.form.make_control({
//             parent: wrapper,
//             df,
//             render_input: true
//         });

//         // save each control so we can access it later
//         frm.custom_controls[df.fieldname] = control;
//     });

//     load_rbs_task_data(frm);
//     attach_dynamic_logic(frm);
//     check_control_event_change(frm);
// }

// function save_rbs_task_data(frm) {
//     let values = {
//         task_date: frm.custom_controls.task_date.get_value(),
//         buyer_name: frm.custom_controls.buyer_name.get_value(),
//         vibe_id: frm.custom_controls.vibe_id.get_value(),
//         buyer_user_name: frm.custom_controls.buyer_user_name.get_value()
//     };

//     // If no child doc exists → create
//     if (!frm.doc.custom_rbs_task_link) {
//         frappe.call({
//             method: "frappe.client.insert",
//             args: {
//                 doc: {
//                     doctype: "RBS Task",
//                     ...values
//                 }
//             },
//             async: false,   // ensure runs before saving
//             callback(r) {
//                 frm.set_value("custom_rbs_task_link", r.message.name);
//             }
//         });
//     }
//     // If exists → update
//     else {
//         frappe.call({
//             method: "frappe.client.set_value",
//             args: {
//                 doctype: "RBS Task",
//                 name: frm.doc.custom_rbs_task_link,
//                 fieldname: values
//             },
//             async: false,
//             callback(r) {
//                 frm.set_value("custom_rbs_task_link", r.message.name);
//                 Object.keys(frm.custom_controls).forEach(fieldname => {
//                     let control = frm.custom_controls[fieldname];
//                     control.set_value(r.message[fieldname]);
//                 });
//             }
//         });
//     }
// }

// function load_rbs_task_data(frm) {
//     frm.__custom_loading = true;  // start loading

//     if (frm.doc.custom_rbs_task_link) {
//         frappe.call({
//             method: "shayona.shayona.doctype.rbs_task.rbs_task.get_rbs_task",
//             args: { name: frm.doc.custom_rbs_task_link },
//             async: false
//         }).then(r => {
//             const data = r.message || {};

//             Object.keys(frm.custom_controls).forEach(fieldname => {
//                 const control = frm.custom_controls[fieldname];
//                 control.set_value(data[fieldname]);  // safe because __custom_loading = true
//                 control.df._last_saved_value = data[fieldname];  // store loaded value for dirty comparison
//             });
//         });
//     }

//     frm.__custom_loading = false;  // end loading
// }

// function check_control_event_change(frm) {
//     Object.keys(frm.custom_controls).forEach(fieldname => {
//         const control = frm.custom_controls[fieldname];

//         const handler = () => {
//             if (frm.__custom_loading) return;

//             const current_val = control.get_value();

//             if (current_val !== control.df._last_saved_value) {
//                 frm.dirty();
//             }
//         };

//         if (fieldname === "task_date") {
//             // listen to both change and blur
//             control.$input.on("change blur", handler);
//         } else {
//             control.$input.on("input change", handler);
//         }
//     });
// }

// function attach_dynamic_logic(frm) {
//     const buyer_control = frm.custom_controls.buyer_name;
//     const vibe_control = frm.custom_controls.vibe_id;

//     if (!buyer_control || !vibe_control) return;

//     const handler = async () => {
//         if (frm.__custom_loading) return;  // skip programmatic changes

//         const buyer_name = buyer_control.get_value();
//         if (!buyer_name) {
//             vibe_control.set_value("");   // clear if no buyer
//             return;
//         }

//         // Fetch Vibe ID from table (RBS Buyer)
//         const r = await frappe.db.get_value("RBS Buyer", { buyer_name }, ["vibe_id"]);
//         vibe_control.set_value(r?.message?.vibe_id || "");
//     };

//     // Attach event
//     buyer_control.$input.on("input change blur", handler);
// }
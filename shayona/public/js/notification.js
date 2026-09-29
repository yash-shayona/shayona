frappe.ui.form.on("Notification", {
    setup(frm) {
        frm.set_query("custom_whatsapp_template", () => ({
            filters: { enabled: 1 },
        }));
    },

    refresh(frm) {
        ensure_whatsapp_channel_option(frm);
        toggle_whatsapp_fields(frm);
    },

    channel(frm) {
        toggle_whatsapp_fields(frm);
    },
});

function ensure_whatsapp_channel_option(frm) {
    const field = frappe.meta.get_docfield("Notification", "channel", frm.doc.name);
    if (!field) return;

    const options = String(field.options || "")
        .split("\n")
        .map((value) => value.trim())
        .filter(Boolean);

    if (!options.includes("WhatsApp")) {
        options.push("WhatsApp");
        frm.set_df_property("channel", "options", options.join("\n"));
    }
}

function toggle_whatsapp_fields(frm) {
    const is_whatsapp = frm.doc.channel === "WhatsApp";

    [
        "message_sb",
        "message",
        "message_examples",
        "view_properties",
        "column_break_25",
        "attach_print",
        "print_format",
        "attach_files",
        "from_attach_field",
        "send_system_notification",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.toggle_display(fieldname, !is_whatsapp);
        }
    });

    [
        "custom_whatsapp_settings_section",
        "custom_whatsapp_template",
        "custom_whatsapp_variables",
    ].forEach((fieldname) => {
        if (frm.fields_dict[fieldname]) {
            frm.toggle_display(fieldname, is_whatsapp);
        }
    });
}

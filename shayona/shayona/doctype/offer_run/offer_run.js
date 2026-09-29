frappe.ui.form.on("Offer Run", {
    refresh(frm) {
        if (!frm.is_new()) {
            return;
        }

        // Offer Run is created by the analysis service, not by a direct Desk save.
        frm.disable_save();

        if (frm.doc.source !== "Desk") {
            frm.set_value("source", "Desk");
        }

        const button = frm.add_custom_button(__("Run Analysis"), () => {
            run_offer_analysis(frm, button);
        });
        button.addClass("btn-primary");
    },
});

async function run_offer_analysis(frm, button) {
    const required_fields = [
        ["company", __("Company")],
        ["goal", __("Goal")],
    ];

    for (const [fieldname, label] of required_fields) {
        if (!frm.doc[fieldname]) {
            frappe.msgprint({
                message: __(
                    "Please select {0} before running the Offer Engine.",
                    [label]
                ),
                indicator: "red",
                title: __("Missing Input"),
            });
            return;
        }
    }

    button.prop("disabled", true);

    try {
        const response = await frappe.call({
            method: "shayona.api.offer_engine.run_analysis",
            type: "POST",
            args: {
                company: frm.doc.company,
                goal: frm.doc.goal,
                customer: frm.doc.customer || null,
                item_code: frm.doc.item_code || null,
                lookback_months: frm.doc.lookback_months || null,
                source: "Desk",
                external_request_id: frm.doc.external_request_id || null,
            },
            freeze: true,
            freeze_message: __("Running Offer Analysis...")
        });

        const result = response && response.message;
        if (!result || !result.name) {
            frappe.throw(__("Offer Analysis completed without returning an Offer Run."));
        }

        frappe.show_alert({
            message: __("Offer Analysis completed: {0}", [result.name]),
            indicator: "green",
        });
        frappe.set_route("Form", "Offer Run", result.name);
    } finally {
        button.prop("disabled", false);
    }
}
frappe.ui.form.on("Sales Order", {
    refresh(frm) {
        if (frm.__simple_mode === undefined) {
            frm.__simple_mode = frm.is_new();
        }

        set_simple_sales_order_mode(frm);
    },
});

function set_simple_sales_order_mode(frm) {
    const simple_mode = frm.is_new() && frm.__simple_mode;
    frappe.msgprint(__(simple_mode ? "On" : "Off"));
    frm.toggle_display(
        [
            "contact_info",
            "currency_and_price_list",
            "pricing_rule_details",
            "taxes_section",
            "payment_schedule_section",
            "more_info",
            "connections_tab",
        ],
        !simple_mode
    );

    if (simple_mode) {
        frm.add_custom_button(__("Open Full Form"), () => {
            frm.__simple_mode = false;
            set_simple_sales_order_mode(frm);
        });
    }
}
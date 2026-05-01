// Copyright (c) 2026, Yash Solanki and contributors
// For license information, please see license.txt

frappe.ui.form.on("Tea Entry", {
    refresh(frm) {

    },

    no_of_cups(frm) {
        set_total_amount(frm);
    }    
});

function set_total_amount(frm) {
    const no_of_cups = frm.doc.no_of_cups || 0;
    const rate_per_cup = frm.doc.rate_per_cup || 0;
    frm.set_value("total_amount", no_of_cups * rate_per_cup);
}
// Copyright (c) 2025, Yash Solanki and contributors
// For license information, please see license.txt

frappe.ui.form.on("Activity Tracker", {
    refresh(frm) {
        render_screenshot_gallery(frm);
    },
});

function render_screenshot_gallery(frm) {
    let html = "<div style='display:flex; flex-wrap:wrap; justify-content:center; gap:15px; margin:10px 0'>";

    (frm.doc.activity_tracker_detail || []).forEach(row => {
        // st_ts add
        let st_ts = row.st_ts ? frappe.datetime.get_time(row.st_ts) : "";

        if (row.screenshot) {
            html += `
            <div style="width:220px; text-align:center;">
                    <div style="
                        width:210px; 
                        overflow:hidden; 
                        border:1px solid #ddd; 
                        border-radius:5px;
                    ">
                        <a href="${row.screenshot}" target="_blank">
                            <img src="${row.screenshot}" style="width:100%; height:100%; object-fit:cover;">
                        </a>
                    </div>
                    <div style="font-size:12px; margin:5px 0 0 0">
                        ${st_ts}
                    </div>
                </div>
            `;
        }
    });

    html += "</div>";
    frm.get_field("screenshot_gallery").$wrapper.html(html);
}
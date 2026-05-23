// Copyright (c) 2025, Yash Solanki and contributors
// For license information, please see license.txt

// Pagination state for screenshot gallery
let screenshot_pagination = {
    current_page: 1,
    items_per_page: 10
};

frappe.ui.form.on("Activity Tracker", {
    refresh(frm) {
        // Reset pagination when form refreshes
        screenshot_pagination.current_page = 1;
        render_screenshot_gallery(frm);
    },
});

function render_screenshot_gallery(frm) {
    const all_items = (frm.doc.activity_tracker_detail || []).filter(row => row.screenshot);
    
    // Calculate pagination
    const start_index = (screenshot_pagination.current_page - 1) * screenshot_pagination.items_per_page;
    const end_index = start_index + screenshot_pagination.items_per_page;
    const paginated_items = all_items.slice(start_index, end_index);
    
    let html = "<div style='display:flex; flex-wrap:wrap; justify-content:center; gap:15px; margin:10px 0'>";

    paginated_items.forEach(row => {
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
    
    // Add pagination controls
    const total_pages = Math.ceil(all_items.length / screenshot_pagination.items_per_page);
    if (total_pages > 1) {
        // Generate page options for dropdown
        let page_options = '';
        for (let i = 1; i <= total_pages; i++) {
            page_options += `<option value="${i}" ${i === screenshot_pagination.current_page ? 'selected' : ''}>Page ${i}</option>`;
        }
        
        html += `
        <div class="pagination-controls" style="text-align:center; margin-top:20px; padding:15px; border-top:1px solid var(--border-color); border-radius:4px; display:flex; align-items:center; justify-content:center; gap:15px; flex-wrap:wrap;">
            <button class="btn btn-sm btn-default btn-prev-screenshots" ${screenshot_pagination.current_page === 1 ? 'disabled' : ''}>
                ← Previous
            </button>
            
            <select class="screenshot-page-select" style="padding:5px 10px; border-radius:3px; border:1px solid var(--border-color); background-color:var(--control-bg); color:var(--text-color); cursor:pointer; font-size:12px;">
                ${page_options}
            </select>
            
            <span style="font-size:12px; color:var(--text-muted); font-weight:500;">
                (${start_index + 1}-${Math.min(end_index, all_items.length)} of ${all_items.length})
            </span>
            
            <button class="btn btn-sm btn-default btn-next-screenshots" ${screenshot_pagination.current_page === total_pages ? 'disabled' : ''}>
                Next →
            </button>
        </div>
        `;
    }
    
    frm.get_field("screenshot_gallery").$wrapper.html(html);
    
    // Attach click events for Previous/Next
    frm.get_field("screenshot_gallery").$wrapper.find(".btn-next-screenshots").on("click", function() {
        if (screenshot_pagination.current_page < total_pages) {
            screenshot_pagination.current_page++;
            render_screenshot_gallery(frm);
        }
    });
    
    frm.get_field("screenshot_gallery").$wrapper.find(".btn-prev-screenshots").on("click", function() {
        if (screenshot_pagination.current_page > 1) {
            screenshot_pagination.current_page--;
            render_screenshot_gallery(frm);
        }
    });
    
    // Attach change event for page dropdown
    frm.get_field("screenshot_gallery").$wrapper.find(".screenshot-page-select").on("change", function() {
        screenshot_pagination.current_page = parseInt($(this).val());
        render_screenshot_gallery(frm);
    });
}
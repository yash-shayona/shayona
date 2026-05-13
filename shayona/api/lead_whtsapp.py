import frappe
@frappe.whitelist(allow_guest=True)
def whatsapp_webhook():
    
    data = frappe.form_dict

    mobile_no   = data.get("mobile_no", "").replace("whatsapp:", "").strip()
    lead_name   = data.get("lead_name", "").strip() or mobile_no
    description = data.get("description", "")
    source      = data.get("source", "WhatsApp")

    if not mobile_no:
        return {"status": "error", "reason": "No mobile number"}

    if frappe.db.get_value("CRM Lead", {"mobile_no": mobile_no}, "name"):
        return {"status": "skipped", "reason": "Lead already exists"}

    frappe.set_user("Administrator")

    lead = frappe.get_doc({
        "doctype"    : "CRM Lead",
        "lead_name"  : lead_name,
        "first_name"  : lead_name,
        "mobile_no"  : mobile_no,
        "source"     : source,
        "description": description,
        "status"        : "New",
    })
    lead.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"status": "success", "lead": lead.name}

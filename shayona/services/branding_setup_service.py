import frappe
import os
from shayona.services.utils_service import attach_file
from frappe.utils.file_manager import save_file

APP_NAME = "Shayona"
APP = "shayona"

APP_PATH = frappe.get_app_path(APP)

IMAGES = {
    "logo": os.path.join(APP_PATH, "public", "images", "logo.png"),
    "favicon": os.path.join(APP_PATH, "public", "images", "favicon.png"),
    "brand": os.path.join(APP_PATH, "public", "images", "brand.png"),
}

# ---------------------------------------------------------
# 🔹 Common Image Setter
# ---------------------------------------------------------
def set_image_field(doc, fieldname, file_path, filename, is_private=1):
    file_url = attach_file(file_path, doc.doctype, doc.name, filename, is_private=is_private)
    if file_url:
        doc.set(fieldname, file_url)


# ---------------------------------------------------------
# 🔹 Setup Branding (Main Entry)
# ---------------------------------------------------------
def setup_branding():
    override_website_settings()
    override_fcrm_settings()
    override_navbar_settings()
    frappe.db.commit()
    print("Branding setup completed successfully.")


# ---------------------------------------------------------
# 🔹 Website Settings Override
# ---------------------------------------------------------
def override_website_settings():
    website_settings = frappe.get_single("Website Settings")

    website_settings.app_name = APP_NAME

    set_image_field(website_settings, "app_logo", IMAGES["logo"], "logo.png", is_private=0)
    set_image_field(website_settings, "favicon", IMAGES["favicon"], "favicon.png", is_private=0)
    set_image_field(website_settings, "banner_image", IMAGES["brand"], "brand.png", is_private=0)
    set_image_field(website_settings, "splash_image", IMAGES["logo"], "logo.png", is_private=0)

    website_settings.save(ignore_permissions=True)

def override_navbar_settings():
    navbar = frappe.get_single("Navbar Settings")

    set_image_field(navbar, "app_logo", IMAGES["brand"], "brand.png", is_private=0)

    navbar.save(ignore_permissions=True)

# ---------------------------------------------------------
# 🔹 FCRM Settings Override
# ---------------------------------------------------------
def override_fcrm_settings():
    fcrm_settings = frappe.get_single("FCRM Settings")

    fcrm_settings.brand_name = APP_NAME

    set_image_field(fcrm_settings, "brand_logo", IMAGES["brand"], "brand.png", is_private=0)
    set_image_field(fcrm_settings, "favicon", IMAGES["favicon"], "favicon.png", is_private=0)

    fcrm_settings.save(ignore_permissions=True)

def cleanup_branding():
    # Clean up Website Settings
    website_settings = frappe.get_single("Website Settings")
    website_settings.app_name = "Frappe"
    website_settings.app_logo = ""
    website_settings.favicon = ""
    website_settings.banner_image = ""
    website_settings.splash_image = ""
    website_settings.save(ignore_permissions=True)

    # Clean up Navbar Settings
    navbar = frappe.get_single("Navbar Settings")
    navbar.app_logo = ""
    navbar.save(ignore_permissions=True)

    # Clean up FCRM Settings
    fcrm_settings = frappe.get_single("FCRM Settings")
    fcrm_settings.brand_name = "Frappe CRM"
    fcrm_settings.brand_logo = ""
    fcrm_settings.favicon = ""
    fcrm_settings.save(ignore_permissions=True)
    
    print("Branding cleanup completed successfully.")
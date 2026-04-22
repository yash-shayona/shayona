import os

import frappe
from frappe.utils.file_manager import get_content_hash

from shayona.services.utils_service import attach_file

APP_NAME = "Shayona"
APP = "shayona"

APP_PATH = frappe.get_app_path(APP)

IMAGES = {
    "logo": os.path.join(APP_PATH, "public", "images", "logo.png"),
    "favicon": os.path.join(APP_PATH, "public", "images", "favicon.ico"),
    "brand": os.path.join(APP_PATH, "public", "images", "brand.png"),
}

BRANDING_IMAGE_FIELDS = {
    "Website Settings": ("app_logo", "favicon", "banner_image", "splash_image"),
    "Navbar Settings": ("app_logo",),
    "FCRM Settings": ("brand_logo", "favicon"),
}


def _get_branding_hashes():
    branding_hashes = set()

    for file_path in IMAGES.values():
        if not os.path.exists(file_path):
            continue
        with open(file_path, "rb") as file_handle:
            branding_hashes.add(get_content_hash(file_handle.read()))

    return branding_hashes


def _delete_file_records(file_names):
    for file_name in file_names:
        try:
            frappe.delete_doc("File", file_name, ignore_permissions=True)
        except frappe.DoesNotExistError:
            continue


def _cleanup_branding_files_for_target_settings():
    branding_hashes = list(_get_branding_hashes())
    if not branding_hashes:
        return

    settings_doctypes = list(BRANDING_IMAGE_FIELDS.keys())
    file_names = frappe.get_all(
        "File",
        filters={
            "content_hash": ["in", branding_hashes],
            "attached_to_doctype": ["in", settings_doctypes],
            "attached_to_name": ["in", settings_doctypes],
        },
        pluck="name",
    )
    _delete_file_records(file_names)


def _cleanup_branding_files_from_site():
    branding_hashes = list(_get_branding_hashes())
    if not branding_hashes:
        return

    file_names = frappe.get_all(
        "File",
        filters={"content_hash": ["in", branding_hashes]},
        pluck="name",
    )
    _delete_file_records(file_names)


def set_image_field(doc, fieldname, file_path, filename, is_private=1, asset_cache=None):
    cache_key = (file_path, filename, is_private)
    file_url = asset_cache.get(cache_key) if asset_cache else None

    if not file_url:
        file_url = attach_file(
            file_path,
            doc.doctype,
            doc.name,
            filename,
            is_private=is_private,
            attached_to_field=fieldname,
        )
        if asset_cache is not None and file_url:
            asset_cache[cache_key] = file_url

    if file_url:
        doc.set(fieldname, file_url)


def setup_branding():
    _cleanup_branding_files_for_target_settings()
    asset_cache = {}

    override_website_settings(asset_cache)
    override_fcrm_settings(asset_cache)
    override_navbar_settings(asset_cache)
    frappe.db.commit()
    print("Branding setup completed successfully.")


def override_website_settings(asset_cache):
    website_settings = frappe.get_single("Website Settings")

    website_settings.app_name = APP_NAME

    set_image_field(website_settings, "app_logo", IMAGES["logo"], "logo.png", is_private=0, asset_cache=asset_cache)
    set_image_field(website_settings, "favicon", IMAGES["favicon"], "favicon.ico", is_private=0, asset_cache=asset_cache)
    set_image_field(
        website_settings,
        "banner_image",
        IMAGES["brand"],
        "brand.png",
        is_private=0,
        asset_cache=asset_cache,
    )
    set_image_field(
        website_settings,
        "splash_image",
        IMAGES["logo"],
        "logo.png",
        is_private=0,
        asset_cache=asset_cache,
    )

    website_settings.save(ignore_permissions=True)


def override_navbar_settings(asset_cache):
    navbar = frappe.get_single("Navbar Settings")

    set_image_field(navbar, "app_logo", IMAGES["brand"], "brand.png", is_private=0, asset_cache=asset_cache)

    navbar.save(ignore_permissions=True)


def override_fcrm_settings(asset_cache):
    fcrm_settings = frappe.get_single("FCRM Settings")

    fcrm_settings.brand_name = APP_NAME

    set_image_field(
        fcrm_settings,
        "brand_logo",
        IMAGES["brand"],
        "brand.png",
        is_private=0,
        asset_cache=asset_cache,
    )
    set_image_field(
        fcrm_settings,
        "favicon",
        IMAGES["favicon"],
        "favicon.ico",
        is_private=0,
        asset_cache=asset_cache,
    )

    fcrm_settings.save(ignore_permissions=True)


def cleanup_branding():
    website_settings = frappe.get_single("Website Settings")
    website_settings.app_name = "Frappe"
    for fieldname in BRANDING_IMAGE_FIELDS["Website Settings"]:
        website_settings.set(fieldname, "")
    website_settings.save(ignore_permissions=True)

    navbar = frappe.get_single("Navbar Settings")
    for fieldname in BRANDING_IMAGE_FIELDS["Navbar Settings"]:
        navbar.set(fieldname, "")
    navbar.save(ignore_permissions=True)

    fcrm_settings = frappe.get_single("FCRM Settings")
    fcrm_settings.brand_name = "Frappe CRM"
    for fieldname in BRANDING_IMAGE_FIELDS["FCRM Settings"]:
        fcrm_settings.set(fieldname, "")
    fcrm_settings.save(ignore_permissions=True)

    _cleanup_branding_files_from_site()

    print("Branding cleanup completed successfully.")

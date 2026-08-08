from __future__ import annotations

import hashlib
import json
import os
import re
from collections import defaultdict
from typing import Any

import frappe
from frappe.utils import now_datetime


APP_NAME = "shayona"
STATE_DOCTYPE = "Shayona Navigation Sync State"
MANIFEST_SCHEMA_VERSION = 1
MANIFEST_PATH = os.path.join(frappe.get_app_path(APP_NAME), "config", "navigation.json")

ALLOWED_ITEM_TYPES = {"Link", "Section Break", "Spacer", "Sidebar Item Group"}
ALLOWED_LINK_TYPES = {"DocType", "Page", "Report", "Workspace", "Dashboard", "URL"}

SIDEBAR_ITEM_FIELDS = (
    "label",
    "type",
    "link_type",
    "link_to",
    "url",
    "icon",
    "child",
    "navigate_to_tab",
    "collapsible",
    "indent",
    "keep_closed",
    "show_arrow",
    "filters",
    "route_options",
)

SIDEBAR_ITEM_DEFAULTS = {
    "label": None,
    "type": "Link",
    "link_type": "DocType",
    "link_to": None,
    "url": None,
    "icon": None,
    "child": 0,
    "navigate_to_tab": None,
    "collapsible": 1,
    "indent": 0,
    "keep_closed": 0,
    "show_arrow": 0,
    "filters": None,
    "route_options": None,
}

DESKTOP_ICON_FIELDS = (
    "icon_type",
    "link_type",
    "link_to",
    "sidebar",
    "icon_image",
    "icon",
    "logo_url",
    "bg_color",
    "hidden",
    "restrict_removal",
    "idx",
    "parent_icon",
    "link",
)

DESKTOP_ICON_DEFAULTS = {
    "icon_type": "Link",
    "link_type": "Workspace Sidebar",
    "link_to": None,
    "sidebar": None,
    "icon_image": None,
    "icon": None,
    "logo_url": None,
    "bg_color": None,
    "hidden": 0,
    "restrict_removal": 0,
    "idx": 0,
    "parent_icon": None,
    "link": None,
}


def sync_navigation() -> dict[str, Any]:
    """Synchronize the app-owned navigation baseline without deleting live-only sidebar rows.

    Intended for hooks.py `after_install` and `after_migrate`.
    No explicit database commit is done; Frappe owns the transaction.
    """
    manifest = _load_manifest()
    _validate_manifest(manifest)

    state = _load_state()
    sidebar_title = manifest["sidebar"]["title"]

    # If the configured sidebar name changed, do not use old row-name ownership state
    # against a different document. The old sidebar is intentionally left untouched.
    previous_sidebar_title = state.get("sidebar_title")
    managed_map = state.get("managed_sidebar_items") or {}
    if previous_sidebar_title and previous_sidebar_title != sidebar_title:
        managed_map = {}

    sidebar_doc, new_managed_map, sidebar_summary = _sync_sidebar(
        manifest["sidebar"], managed_map
    )
    icon_doc = _sync_desktop_icon(manifest["desktop_icon"], sidebar_doc.name)

    manifest_hash = _manifest_hash(manifest)
    _save_state(
        manifest_hash=manifest_hash,
        sidebar_title=sidebar_doc.name,
        desktop_icon_label=icon_doc.name,
        managed_map=new_managed_map,
    )
    _clear_navigation_caches()

    result = {
        "sidebar": sidebar_doc.name,
        "desktop_icon": icon_doc.name,
        "manifest_hash": manifest_hash,
        **sidebar_summary,
    }
    frappe.logger(APP_NAME).info("Hybrid navigation sync complete: %s", result)
    return result


def capture_navigation(
    sidebar_title: str = "Shayona", desktop_icon_label: str | None = None
) -> dict[str, Any]:
    """Capture local editable Desktop Icon + Workspace Sidebar into Git-tracked manifest.

    Run only on a development site:
      bench --site <site> execute shayona.setup.navigation.capture_navigation

    Optional kwargs through bench execute can be supplied when names differ.
    """
    if not frappe.conf.developer_mode:
        frappe.throw("capture_navigation is allowed only when developer_mode is enabled")

    desktop_icon_label = desktop_icon_label or sidebar_title
    sidebar = frappe.get_doc("Workspace Sidebar", sidebar_title)
    icon = frappe.get_doc("Desktop Icon", desktop_icon_label)

    old_manifest = _load_manifest(allow_missing=True) or {}
    reusable_keys = _old_keys_by_signature(old_manifest)
    used_keys: set[str] = set()

    captured_items = []
    for row in sidebar.items:
        item = _capture_sidebar_item(row)
        signature = _item_signature(item)
        old_key = reusable_keys.get(signature)
        key = old_key if old_key and old_key not in used_keys else _make_item_key(item, used_keys)
        used_keys.add(key)
        captured_items.append({"key": key, **item})

    desktop_icon = {
        "label": icon.label,
        **{field: _json_safe(getattr(icon, field, None)) for field in DESKTOP_ICON_FIELDS},
        "roles": [row.role for row in icon.get("roles", []) if row.role],
    }
    desktop_icon = {k: v for k, v in desktop_icon.items() if v not in (None, "")}

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "sidebar": {
            "title": sidebar.title,
            "header_icon": sidebar.header_icon,
            "module_onboarding": sidebar.module_onboarding,
            "module": sidebar.module,
            "items": captured_items,
        },
        "desktop_icon": desktop_icon,
    }

    _validate_manifest(manifest)
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    result = {
        "manifest_path": MANIFEST_PATH,
        "sidebar": sidebar.name,
        "desktop_icon": icon.name,
        "item_count": len(captured_items),
    }
    print(json.dumps(result, indent=2))
    return result


def navigation_status() -> dict[str, Any]:
    """Return a small diagnostic snapshot; safe to run with bench execute."""
    manifest = _load_manifest()
    _validate_manifest(manifest)
    state = _load_state()
    sidebar_title = manifest["sidebar"]["title"]
    icon_label = manifest["desktop_icon"]["label"]

    sidebar_exists = bool(frappe.db.exists("Workspace Sidebar", sidebar_title))
    icon_exists = bool(frappe.db.exists("Desktop Icon", icon_label))

    live_count = 0
    managed_count = 0
    if sidebar_exists:
        sidebar = frappe.get_doc("Workspace Sidebar", sidebar_title)
        managed_names = set((state.get("managed_sidebar_items") or {}).values())
        for row in sidebar.items:
            if row.name in managed_names:
                managed_count += 1
            else:
                live_count += 1

    result = {
        "manifest_path": MANIFEST_PATH,
        "manifest_hash": _manifest_hash(manifest),
        "last_synced_hash": state.get("manifest_hash"),
        "sidebar_exists": sidebar_exists,
        "desktop_icon_exists": icon_exists,
        "managed_rows": managed_count,
        "live_only_rows": live_count,
        "last_sync_on": state.get("last_sync_on"),
    }
    print(json.dumps(result, indent=2, default=str))
    return result


def _sync_sidebar(
    sidebar_config: dict[str, Any], old_managed_map: dict[str, str]
) -> tuple[Any, dict[str, str], dict[str, int]]:
    title = sidebar_config["title"]
    exists = frappe.db.exists("Workspace Sidebar", title)
    sidebar = frappe.get_doc("Workspace Sidebar", title) if exists else frappe.new_doc("Workspace Sidebar")

    if not exists:
        sidebar.title = title

    # Deliberately keep this navigation editable in production.
    sidebar.standard = 0
    sidebar.app = None
    sidebar.for_user = None
    sidebar.header_icon = sidebar_config.get("header_icon")
    sidebar.module_onboarding = sidebar_config.get("module_onboarding")
    if "module" in sidebar_config:
        sidebar.module = sidebar_config.get("module")

    current_rows = list(sidebar.get("items") or [])
    current_by_name = {row.name: row for row in current_rows if row.name}

    manifest_items = sidebar_config.get("items") or []
    manifest_keys = {item["key"] for item in manifest_items}

    claimed_existing_names: set[str] = set()
    managed_rows: dict[str, Any] = {}
    managed_existing_name_to_key: dict[str, str] = {}
    added = 0
    adopted = 0
    updated = 0

    for item in manifest_items:
        key = item["key"]
        row = None
        previous_row_name = old_managed_map.get(key)

        if previous_row_name and previous_row_name in current_by_name:
            row = current_by_name[previous_row_name]
            claimed_existing_names.add(previous_row_name)
            managed_existing_name_to_key[previous_row_name] = key
            updated += 1
        else:
            row = _find_semantic_match(item, current_rows, claimed_existing_names)
            if row:
                claimed_existing_names.add(row.name)
                managed_existing_name_to_key[row.name] = key
                adopted += 1
            else:
                row = frappe.new_doc("Workspace Sidebar Item")
                added += 1

        _apply_sidebar_item(row, item)
        managed_rows[key] = row

    obsolete_names = {
        row_name
        for key, row_name in old_managed_map.items()
        if key not in manifest_keys and row_name
    }

    unmanaged_rows = [
        row
        for row in current_rows
        if row.name not in claimed_existing_names and row.name not in obsolete_names
    ]
    unmanaged_names = {row.name for row in unmanaged_rows}

    # Keep live-only rows near the app-owned item that preceded them before the sync.
    live_rows_by_anchor: dict[str | None, list[Any]] = defaultdict(list)
    last_anchor: str | None = None
    for row in current_rows:
        if row.name in managed_existing_name_to_key:
            last_anchor = managed_existing_name_to_key[row.name]
            continue
        if row.name in unmanaged_names:
            live_rows_by_anchor[last_anchor].append(row)

    final_rows = []
    for item in manifest_items:
        key = item["key"]
        final_rows.append(managed_rows[key])
        final_rows.extend(live_rows_by_anchor.pop(key, []))

    # Rows that were before the first managed item, or whose old anchor disappeared,
    # are preserved at the tail rather than being deleted.
    final_rows.extend(live_rows_by_anchor.pop(None, []))
    for leftovers in live_rows_by_anchor.values():
        final_rows.extend(leftovers)

    for index, row in enumerate(final_rows, start=1):
        row.idx = index

    sidebar.items = final_rows
    if exists:
        sidebar.save(ignore_permissions=True)
    else:
        sidebar.insert(ignore_permissions=True)

    # Non-standard Desktop Icons are globally visible only when owner is Administrator
    # (or the current user). Use Administrator for a site-wide app icon/sidebar baseline.
    frappe.db.set_value(
        "Workspace Sidebar", sidebar.name, "owner", "Administrator", update_modified=False
    )

    new_managed_map = {key: row.name for key, row in managed_rows.items()}
    summary = {
        "managed_items": len(manifest_items),
        "live_only_items_preserved": len(unmanaged_rows),
        "managed_added": added,
        "managed_adopted": adopted,
        "managed_updated": updated,
        "managed_removed": len(obsolete_names & set(current_by_name)),
    }
    return sidebar, new_managed_map, summary


def _sync_desktop_icon(icon_config: dict[str, Any], sidebar_name: str):
    label = icon_config["label"]
    exists = frappe.db.exists("Desktop Icon", label)
    icon = frappe.get_doc("Desktop Icon", label) if exists else frappe.new_doc("Desktop Icon")

    if not exists:
        icon.label = label

    # Important for the hybrid pattern: never standardize this production record.
    icon.standard = 0
    icon.app = None

    for field, default in DESKTOP_ICON_DEFAULTS.items():
        setattr(icon, field, default)
    for field in DESKTOP_ICON_FIELDS:
        if field in icon_config:
            setattr(icon, field, icon_config.get(field))

    # Force the supported wiring for this design.
    icon.icon_type = "Link"
    icon.link_type = "Workspace Sidebar"
    icon.link_to = sidebar_name
    icon.sidebar = sidebar_name
    icon.link = None

    if "roles" in icon_config:
        icon.set("roles", [])
        for role in icon_config.get("roles") or []:
            icon.append("roles", {"role": role})

    if exists:
        icon.save(ignore_permissions=True)
    else:
        icon.insert(ignore_permissions=True)

    frappe.db.set_value("Desktop Icon", icon.name, "owner", "Administrator", update_modified=False)
    return icon


def _apply_sidebar_item(row, item: dict[str, Any]) -> None:
    for field, default in SIDEBAR_ITEM_DEFAULTS.items():
        setattr(row, field, default)

    for field in SIDEBAR_ITEM_FIELDS:
        if field not in item:
            continue
        value = item.get(field)
        if field in {"filters", "route_options"} and isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        setattr(row, field, value)

    if row.type != "Link":
        row.link_to = None
        row.url = None
        row.navigate_to_tab = None
        row.filters = None
        row.route_options = None
    elif row.link_type == "URL":
        row.link_to = None
    else:
        row.url = None


def _find_semantic_match(item, current_rows, claimed_existing_names: set[str]):
    wanted = _item_signature(item)
    for row in current_rows:
        if not row.name or row.name in claimed_existing_names:
            continue
        if _item_signature(row) == wanted:
            return row
    return None


def _item_signature(item_or_row) -> str:
    get = item_or_row.get if isinstance(item_or_row, dict) else lambda key, default=None: getattr(item_or_row, key, default)
    item_type = get("type") or "Link"

    if item_type == "Link":
        payload = {
            "type": "Link",
            "link_type": get("link_type") or "DocType",
            "link_to": get("link_to"),
            "url": get("url"),
            "navigate_to_tab": get("navigate_to_tab"),
            "filters": _canonical_json_value(get("filters")),
            "route_options": _canonical_json_value(get("route_options")),
        }
    else:
        payload = {
            "type": item_type,
            "label": get("label"),
        }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _capture_sidebar_item(row) -> dict[str, Any]:
    result = {}
    for field in SIDEBAR_ITEM_FIELDS:
        value = getattr(row, field, None)
        if field in {"filters", "route_options"}:
            value = _canonical_json_value(value)
        value = _json_safe(value)
        if value not in (None, ""):
            result[field] = value
    return result


def _old_keys_by_signature(old_manifest: dict[str, Any]) -> dict[str, str]:
    result = {}
    for item in (old_manifest.get("sidebar") or {}).get("items") or []:
        key = item.get("key")
        if key:
            result.setdefault(_item_signature(item), key)
    return result


def _make_item_key(item: dict[str, Any], used_keys: set[str]) -> str:
    item_type = item.get("type") or "Link"
    if item_type == "Link":
        target = item.get("link_to") or item.get("url") or item.get("label") or "link"
        base = f"link.{item.get('link_type', 'doctype')}.{target}"
    elif item_type == "Section Break":
        base = f"section.{item.get('label') or 'section'}"
    elif item_type == "Sidebar Item Group":
        base = f"group.{item.get('label') or 'group'}"
    else:
        base = f"spacer.{item.get('label') or 'spacer'}"

    base = re.sub(r"[^a-z0-9]+", ".", base.lower()).strip(".") or "item"
    key = base
    number = 2
    while key in used_keys:
        key = f"{base}.{number}"
        number += 1
    return key


def _load_manifest(allow_missing: bool = False) -> dict[str, Any] | None:
    if not os.path.exists(MANIFEST_PATH):
        if allow_missing:
            return None
        frappe.throw(f"Navigation manifest not found: {MANIFEST_PATH}")

    with open(MANIFEST_PATH, encoding="utf-8") as handle:
        return json.load(handle)


def _validate_manifest(manifest: dict[str, Any]) -> None:
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        frappe.throw(
            f"Unsupported navigation manifest schema_version: {manifest.get('schema_version')}"
        )

    sidebar = manifest.get("sidebar") or {}
    icon = manifest.get("desktop_icon") or {}
    title = sidebar.get("title")
    label = icon.get("label")

    if not title:
        frappe.throw("navigation.json: sidebar.title is required")
    if not label:
        frappe.throw("navigation.json: desktop_icon.label is required")

    # Frappe v16 Desktop Icon permission logic looks up sidebar boot data by icon label.
    # Keeping label == sidebar title avoids a valid sidebar being hidden by that lookup.
    if label != title:
        frappe.throw("For this pattern desktop_icon.label must equal sidebar.title")

    keys: set[str] = set()
    for position, item in enumerate(sidebar.get("items") or [], start=1):
        key = item.get("key")
        if not key:
            frappe.throw(f"navigation.json: sidebar item #{position} is missing key")
        if key in keys:
            frappe.throw(f"navigation.json: duplicate sidebar item key: {key}")
        keys.add(key)

        item_type = item.get("type") or "Link"
        if item_type not in ALLOWED_ITEM_TYPES:
            frappe.throw(f"navigation.json: invalid type '{item_type}' for key '{key}'")

        if item_type == "Link":
            link_type = item.get("link_type") or "DocType"
            if link_type not in ALLOWED_LINK_TYPES:
                frappe.throw(f"navigation.json: invalid link_type '{link_type}' for key '{key}'")
            if link_type == "URL":
                if not item.get("url"):
                    frappe.throw(f"navigation.json: URL item '{key}' requires url")
            elif not item.get("link_to"):
                frappe.throw(f"navigation.json: link item '{key}' requires link_to")

        for json_field in ("filters", "route_options"):
            value = item.get(json_field)
            if isinstance(value, str) and value.strip():
                try:
                    json.loads(value)
                except json.JSONDecodeError:
                    frappe.throw(f"navigation.json: {json_field} for '{key}' is not valid JSON")

    if icon.get("link_type") not in (None, "Workspace Sidebar"):
        frappe.throw("desktop_icon.link_type must be 'Workspace Sidebar'")
    if icon.get("icon_type") not in (None, "Link"):
        frappe.throw("desktop_icon.icon_type must be 'Link'")


def _load_state() -> dict[str, Any]:
    if not frappe.db.exists("DocType", STATE_DOCTYPE):
        return {}

    state = frappe.get_single(STATE_DOCTYPE)
    try:
        managed_items = json.loads(state.managed_sidebar_items or "{}")
    except json.JSONDecodeError:
        managed_items = {}

    return {
        "schema_version": state.schema_version,
        "manifest_hash": state.manifest_hash,
        "sidebar_title": state.sidebar_title,
        "desktop_icon_label": state.desktop_icon_label,
        "managed_sidebar_items": managed_items,
        "last_sync_on": state.last_sync_on,
    }


def _save_state(
    *, manifest_hash: str, sidebar_title: str, desktop_icon_label: str, managed_map: dict[str, str]
) -> None:
    if not frappe.db.exists("DocType", STATE_DOCTYPE):
        frappe.logger(APP_NAME).warning(
            "%s does not exist; navigation synced without persistent ownership state", STATE_DOCTYPE
        )
        return

    state = frappe.get_single(STATE_DOCTYPE)
    state.schema_version = MANIFEST_SCHEMA_VERSION
    state.manifest_hash = manifest_hash
    state.sidebar_title = sidebar_title
    state.desktop_icon_label = desktop_icon_label
    state.managed_sidebar_items = json.dumps(managed_map, sort_keys=True)
    state.last_sync_on = now_datetime()
    state.save(ignore_permissions=True)


def _manifest_hash(manifest: dict[str, Any]) -> str:
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _canonical_json_value(value):
    if value in (None, ""):
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _json_safe(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _clear_navigation_caches() -> None:
    # Mirrors the broad cache invalidation used by Frappe for standard Desktop Icon updates.
    frappe.cache.delete_key("desktop_icons")
    frappe.cache.delete_key("bootinfo")

import json
import uuid
from pathlib import Path

import frappe
from frappe.utils import get_datetime, getdate
from frappe.utils.file_manager import save_file

from shayona.services.aes_decrypt import decrypt_payload


def get_tracker_upload_queue() -> str:
    return frappe.get_site_config().get("activity_tracker_upload_queue", "long")


def get_tracker_upload_timeout() -> int:
    timeout = frappe.get_site_config().get("activity_tracker_upload_timeout", 1800)
    try:
        return max(int(timeout), 60)
    except (TypeError, ValueError):
        return 1800


def _get_upload_root() -> Path:
    root = Path(frappe.get_site_path("private", "files", "tracker_uploads"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _manifest_path(staged_dir: Path) -> Path:
    return staged_dir / "manifest.json"


def _save_uploaded_file(target_path: Path, uploaded_file) -> None:
    uploaded_file.stream.seek(0)
    with open(target_path, "wb") as handle:
        handle.write(uploaded_file.stream.read())


def _cleanup_staged_dir(staged_dir: Path) -> None:
    if not staged_dir.exists():
        return

    for child in staged_dir.iterdir():
        if child.is_dir():
            _cleanup_staged_dir(child)
        else:
            child.unlink(missing_ok=True)

    staged_dir.rmdir()


def stage_uploads(user_id: str, event_files: list, screenshot_files: list, screenshots_meta: list) -> tuple[str, Path]:
    upload_id = uuid.uuid4().hex
    staged_dir = _get_upload_root() / upload_id
    staged_dir.mkdir(parents=True, exist_ok=True)

    screenshot_meta_map = {
        item.get("fieldname"): item
        for item in screenshots_meta
        if isinstance(item, dict) and item.get("fieldname")
    }

    manifest = {
        "upload_id": upload_id,
        "user_id": user_id,
        "event_files": [],
        "screenshots": [],
    }

    for index, (_, uploaded_file) in enumerate(event_files):
        filename = f"event_{index:04d}.json.enc"
        target_path = staged_dir / filename
        _save_uploaded_file(target_path, uploaded_file)
        manifest["event_files"].append(filename)

    for index, (fieldname, uploaded_file) in enumerate(screenshot_files):
        original_name = Path(uploaded_file.filename or f"screenshot_{index}.png").name
        suffix = Path(original_name).suffix or ".png"
        filename = f"screenshot_{index:04d}{suffix}"
        target_path = staged_dir / filename
        _save_uploaded_file(target_path, uploaded_file)

        meta = screenshot_meta_map.get(fieldname, {})
        manifest["screenshots"].append(
            {
                "fieldname": fieldname,
                "filename": filename,
                "original_name": original_name,
                "captured_at": meta.get("captured_at"),
            }
        )

    with open(_manifest_path(staged_dir), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle)

    return upload_id, staged_dir


def enqueue_activity_upload(user_id: str, event_files: list, screenshot_files: list, screenshots_meta: list) -> str:
    upload_id, staged_dir = stage_uploads(user_id, event_files, screenshot_files, screenshots_meta)

    frappe.enqueue(
        "shayona.services.tracker_processor.process_staged_activity_upload",
        queue=get_tracker_upload_queue(),
        timeout=get_tracker_upload_timeout(),
        job_name=f"tracker-upload-{upload_id}",
        upload_id=upload_id,
        staged_dir=str(staged_dir),
        user_id=user_id,
    )

    return upload_id


def resolve_tracker_user(user_id: str) -> str:
    return user_id if frappe.db.exists("User", user_id) else frappe.get_value("User", {"name": user_id})


def get_or_create_tracker(user_id, date):
    user = resolve_tracker_user(user_id)
    employee = frappe.get_value("Employee", {"user_id": user}, "name")
    timesheet = frappe.get_value("Timesheet", {"employee": employee, "start_date": date}, "name")
    filters = {"user": user or user_id, "date": date}

    tracker_name = frappe.get_value(
        "Activity Tracker",
        filters,
        ["name", "employee", "timesheet"],
        as_dict=True,
    )

    if tracker_name:
        if not tracker_name.employee:
            frappe.db.set_value("Activity Tracker", tracker_name.name, "employee", employee)
        if not tracker_name.timesheet:
            frappe.db.set_value("Activity Tracker", tracker_name.name, "timesheet", timesheet)
        return frappe.get_doc("Activity Tracker", tracker_name.name)

    doc = frappe.get_doc(
        {
            "doctype": "Activity Tracker",
            "user": user,
            "employee": employee or None,
            "date": date,
            "timesheet": timesheet,
            "total_idle_time_hrs": 0,
            "total_idle_time_mins": 0,
            "activity_tracker_detail": [],
        }
    )
    doc.insert(ignore_permissions=True)
    return doc


def _get_tracker_context(user_id: str, event_date: str, tracker_map: dict) -> dict:
    tracker_context = tracker_map.get(event_date)
    if tracker_context:
        return tracker_context

    tracker = get_or_create_tracker(user_id, event_date)
    existing_event_ids = set(
        frappe.get_all(
            "Activity Tracker Detail",
            filters={"parent": tracker.name},
            pluck="event_id",
        )
    )

    tracker_context = {
        "tracker": tracker,
        "existing_event_ids": existing_event_ids,
    }
    tracker_map[event_date] = tracker_context
    return tracker_context


def process_activity_payload(user_id, payload, tracker_map):
    plaintext = decrypt_payload(payload)
    events = json.loads(plaintext)

    for event in events:
        event_date = event.get("date")
        if not event_date:
            continue

        tracker_context = _get_tracker_context(user_id, event_date, tracker_map)
        tracker = tracker_context["tracker"]
        existing_event_ids = tracker_context["existing_event_ids"]

        event_id = event.get("event_id", "")
        if event_id and event_id in existing_event_ids:
            continue

        tracker.append(
            "activity_tracker_detail",
            {
                "active_window": event.get("active_window", ""),
                "idle_time_sec": float(event.get("idle_seconds", 0) or 0),
                "mouse_count": event.get("mouse_presses", 0),
                "keyboard_count": event.get("keyboard_presses", 0),
                "timestamp": event.get("timestamp"),
                "event_id": event_id,
            },
        )

        if event_id:
            existing_event_ids.add(event_id)

        tracker.total_idle_time_hrs += float(event.get("idle_seconds", 0) or 0) / 3600
        tracker.total_idle_time_mins += float(event.get("idle_seconds", 0) or 0) / 60


def save_pending_trackers(tracker_map: dict) -> None:
    for tracker_context in tracker_map.values():
        tracker_context["tracker"].save(ignore_permissions=True)
    frappe.db.commit()


def _find_best_detail_row(tracker, screenshot_ts):
    best_row = None
    best_delta = None

    for row in tracker.activity_tracker_detail:
        if not row.timestamp:
            continue

        try:
            row_ts = get_datetime(row.timestamp)
        except Exception:
            continue

        delta = abs((row_ts - screenshot_ts).total_seconds())
        if best_delta is None or delta < best_delta:
            best_row = row
            best_delta = delta

    return best_row


def attach_screenshot_to_tracker(user_id: str, tracker_map: dict, screenshot_entry: dict, staged_dir: Path) -> None:
    captured_at = screenshot_entry.get("captured_at")
    if not captured_at:
        return

    screenshot_ts = get_datetime(captured_at)
    tracker_date = getdate(screenshot_ts).isoformat()
    tracker_context = tracker_map.get(tracker_date)
    resolved_user = resolve_tracker_user(user_id)

    if not tracker_context:
        tracker_name = frappe.get_value(
            "Activity Tracker",
            {"user": resolved_user or user_id, "date": tracker_date},
            "name",
        )
        if not tracker_name:
            return

        tracker_context = {
            "tracker": frappe.get_doc("Activity Tracker", tracker_name),
            "existing_event_ids": set(),
        }
        tracker_map[tracker_date] = tracker_context

    tracker = tracker_context["tracker"]
    screenshot_path = staged_dir / screenshot_entry["filename"]
    if not screenshot_path.exists():
        return

    with open(screenshot_path, "rb") as handle:
        content = handle.read()

    saved_file = save_file(
        screenshot_entry.get("original_name") or screenshot_path.name,
        content,
        "Activity Tracker",
        tracker.name,
        is_private=1,
    )

    detail_row = _find_best_detail_row(tracker, screenshot_ts)
    if detail_row:
        detail_row.screenshot = saved_file.file_url
        detail_row.st_ts = captured_at
        tracker.save(ignore_permissions=True)
        frappe.db.commit()


def process_staged_activity_upload(upload_id: str, staged_dir: str, user_id: str) -> None:
    staged_path = Path(staged_dir)

    try:
        with open(_manifest_path(staged_path), "r", encoding="utf-8") as handle:
            manifest = json.load(handle)

        tracker_map = {}
        for filename in manifest.get("event_files", []):
            event_path = staged_path / filename
            if not event_path.exists():
                continue

            with open(event_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)

            process_activity_payload(user_id, payload, tracker_map)

        if tracker_map:
            save_pending_trackers(tracker_map)

        for screenshot_entry in manifest.get("screenshots", []):
            attach_screenshot_to_tracker(user_id, tracker_map, screenshot_entry, staged_path)

        _cleanup_staged_dir(staged_path)
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"ACTIVITY TRACKER UPLOAD FAILED {upload_id}")
        raise

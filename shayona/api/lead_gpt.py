import base64
import json
import mimetypes
import os
import re
from typing import Any

import frappe
import requests
from frappe.utils import now_datetime

OPENAI_RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
EXTRACT_TOOL_NAME = "extract_business_card_lead_minimal"

BUSINESS_CARD_JOB_QUEUE = "long"
BUSINESS_CARD_JOB_TIMEOUT = 900
BUSINESS_CARD_STATUS_TTL_SECONDS = 60 * 60 * 24

ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}

EXTRACTION_SYSTEM_PROMPT = (
    "You are a strict business card extractor.\n"
    "Extract ONLY these fields and return null when unknown:\n"
    "full_name, first_name, last_name, website, email, mobile_no, job_title.\n\n"
    "CRITICAL REQUIREMENTS:\n"
    "1) first_name and mobile_no are mandatory for lead creation. If uncertain, return null.\n"
    "2) Do not fabricate values.\n"
    "3) Keep email lowercase.\n"
    "4) website should include scheme; if missing, use https://.\n"
    "5) Return English text where possible.\n\n"
    "MOBILE NUMBER SELECTION RULES:\n"
    "- If multiple numbers exist, prefer personal mobile over landline.\n"
    "- Valid examples:\n"
    "  a) +91 8469511356 -> +918469511356\n"
    "  b) 8469511356 -> 8469511356\n"
    "  c) 076-232323 -> treat as mobile_no\n"
    "  d) foreign with country code (e.g., +44..., +1...) is valid mobile_no\n"
    "- mobile_no must contain only digits and optional leading +.\n"
)


@frappe.whitelist(allow_guest=True)
def create_lead_from_business_card():
    try:
        image_bytes, mime_type, filename = _get_uploaded_image_content()
        if not image_bytes:
            frappe.local.response["http_status_code"] = 400
            return {"status": "error", "message": "image file is required in form-data"}

        if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
            frappe.local.response["http_status_code"] = 400
            return {
                "status": "error",
                "message": "unsupported image type. allowed: jpeg, png, webp",
            }

        request_id = frappe.generate_hash(length=16)
        requested_by = frappe.session.user if frappe.session.user != "Guest" else None

        file_doc = _save_business_card_file(
            image_bytes=image_bytes,
            filename=filename,
            request_id=request_id,
        )

        _set_job_status(
            request_id,
            {
                "request_id": request_id,
                "status": "Queued",
                "queued_on": str(now_datetime()),
                "requested_by": requested_by,
                "lead_name": None,
                "error_message": None,
                "result": {},
            },
        )

        job = frappe.enqueue(
            "praveg.api.lead_gpt.process_business_card_job",
            queue=BUSINESS_CARD_JOB_QUEUE,
            timeout=BUSINESS_CARD_JOB_TIMEOUT,
            enqueue_after_commit=True,
            request_id=request_id,
            file_docname=file_doc.name,
            requested_by=requested_by,
        )

        job_id = getattr(job, "id", None) if job else None
        if job_id:
            status_data = _get_job_status(request_id) or {}
            status_data["background_job_id"] = job_id
            _set_job_status(request_id, status_data)

        frappe.db.commit()

        # RN flow: immediate ack only
        return {
            "status": "accepted",
            "message": "Business card request submitted successfully",
            "request_id": request_id,
            "background_job_id": job_id,
        }

    except Exception:
        frappe.log_error(frappe.get_traceback(), "Lead GPT Queue API Error")
        frappe.local.response["http_status_code"] = 500
        return {"status": "error", "message": "Internal Server Error"}


@frappe.whitelist(allow_guest=True)
def get_business_card_job_status(request_id: str):
    if not request_id:
        frappe.throw("request_id is required")

    data = _get_job_status(request_id)
    if not data:
        return {
            "status": "not_found",
            "message": "No cached status found for this request_id (may be expired).",
        }

    return {"status": "success", "data": data}


def process_business_card_job(request_id: str, file_docname: str, requested_by: str | None = None):
    try:
        _patch_job_status(
            request_id, {"status": "Processing", "started_on": str(now_datetime())}
        )

        file_doc = frappe.get_doc("File", file_docname)
        image_bytes = file_doc.get_content()
        if isinstance(image_bytes, str):
            image_bytes = image_bytes.encode("utf-8")

        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = _get_file_mime_type(file_doc)

        extracted = _extract_structured_fields_via_openai(image_b64=image_b64, mime_type=mime_type)
        extracted = _normalize_extracted(extracted)
        _rename_and_move_business_card(file_doc, extracted.get("first_name"))


        duplicate_lead = _find_duplicate_lead(extracted)
        if duplicate_lead:
            _attach_business_card_to_lead(duplicate_lead, file_doc)
            _patch_job_status(
                request_id,
                {
                    "status": "Duplicate",
                    "lead_name": duplicate_lead,
                    "completed_on": str(now_datetime()),
                    "result": {
                        "reason": "lead_exists",
                        "lead_name": duplicate_lead,
                        "card_details": extracted,
                    },
                },
            )
            frappe.db.commit()
            return

        lead = _insert_crm_lead(extracted=extracted, owner_user=requested_by)
        _attach_business_card_to_lead(lead.name, file_doc)

        _patch_job_status(
            request_id,
            {
                "status": "Success",
                "lead_name": lead.name,
                "completed_on": str(now_datetime()),
                "result": {
                    "lead_name": lead.name,
                    "card_details": extracted,
                },
            },
        )

        frappe.db.commit()

    except Exception:
        traceback_text = frappe.get_traceback()
        frappe.log_error(traceback_text, f"Lead GPT Background Job Failed: {request_id}")
        _patch_job_status(
            request_id,
            {
                "status": "Failed",
                "completed_on": str(now_datetime()),
                "error_message": "Background processing failed. Check Error Log.",
            },
        )
        frappe.db.commit()


def _status_cache_key(request_id: str) -> str:
    return f"business_card_job_status::{request_id}"


def _set_job_status(request_id: str, payload: dict[str, Any]):
    frappe.cache().set_value(
        _status_cache_key(request_id),
        json.dumps(payload),
        expires_in_sec=BUSINESS_CARD_STATUS_TTL_SECONDS,
    )


def _get_job_status(request_id: str):
    raw = frappe.cache().get_value(_status_cache_key(request_id))
    if not raw:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {"status": "unknown", "raw": raw}
    return raw


def _patch_job_status(request_id: str, updates: dict[str, Any]):
    current = _get_job_status(request_id) or {"request_id": request_id}
    current.update(updates)
    _set_job_status(request_id, current)


def _normalize_image_mime_type(raw_mime: str | None, filename: str | None = None) -> str:
    value = (raw_mime or "").strip().lower()
    ext_map = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }

    if value in ext_map:
        return ext_map[value]

    if value.startswith("image/"):
        subtype = value.split("/", 1)[1].strip()
        if subtype == "jpg":
            subtype = "jpeg"
        return f"image/{subtype}"

    if filename:
        guessed, _ = mimetypes.guess_type(filename)
        if guessed and guessed.startswith("image/"):
            return guessed.lower()

    return "image/jpeg"


def _get_file_mime_type(file_doc) -> str:
    raw = getattr(file_doc, "file_type", None) or getattr(file_doc, "mime_type", None) or None
    filename = getattr(file_doc, "file_name", None) or getattr(file_doc, "file_url", None)
    return _normalize_image_mime_type(raw, filename)


def _get_uploaded_image_content():
    req = frappe.request
    files = (req.files or {}) if req else {}
    uploaded = files.get("image") or files.get("file")

    if not uploaded:
        return None, None, None

    content = uploaded.read()
    if not content:
        return None, None, None

    mime_type = _normalize_image_mime_type(getattr(uploaded, "mimetype", None), getattr(uploaded, "filename", None))
    filename = getattr(uploaded, "filename", None)
    return content, mime_type, filename


def _get_openai_settings():
    if not frappe.db.exists("DocType", "CRM Business Card AI Settings"):
        raise RuntimeError("CRM Business Card AI Settings doctype not found")

    settings = frappe.get_cached_doc("CRM Business Card AI Settings", "CRM Business Card AI Settings")
    if not getattr(settings, "enabled", 0):
        raise RuntimeError("Business Card AI is disabled")

    api_key = settings.get_password("openai_api_key") if hasattr(settings, "get_password") else None
    model = (getattr(settings, "openai_model", None) or "gpt-5.4-mini").strip()
    timeout_sec = int(getattr(settings, "request_timeout_sec", 90) or 90)

    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")

    return {
        "api_key": api_key,
        "model": model,
        "timeout_sec": timeout_sec,
    }


def _extract_structured_fields_via_openai(image_b64: str, mime_type: str):
    conf = _get_openai_settings()

    payload = {
        "model": conf["model"],
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": EXTRACTION_SYSTEM_PROMPT}],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Extract lead fields from this business card image."},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{image_b64}",
                        "detail": "high",
                    },
                ],
            },
        ],
        "tools": [_lead_extract_tool_schema()],
        "tool_choice": {"type": "function", "name": EXTRACT_TOOL_NAME},
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_ENDPOINT,
            headers={
                "Authorization": f"Bearer {conf['api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=conf["timeout_sec"],
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "OpenAI API Error - Business Card")
        raise RuntimeError("OpenAI card extraction failed")

    if not response.ok:
        frappe.log_error(response.text or "unknown_openai_error", "OpenAI API Error - Business Card")
        raise RuntimeError("OpenAI card extraction failed")

    try:
        response_json = response.json()
    except Exception:
        response_json = {}

    extracted = _extract_function_args(response_json)
    if not extracted:
        raise RuntimeError("Could not extract structured data from card")
    return extracted


def _lead_extract_tool_schema():
    return {
        "type": "function",
        "name": EXTRACT_TOOL_NAME,
        "description": "Extract minimal CRM lead fields from a business card image.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": ["string", "null"]},
                "first_name": {"type": ["string", "null"]},
                "last_name": {"type": ["string", "null"]},
                "website": {"type": ["string", "null"]},
                "email": {"type": ["string", "null"]},
                "mobile_no": {"type": ["string", "null"]},
                "job_title": {"type": ["string", "null"]},
            },
            "required": [
                "full_name",
                "first_name",
                "last_name",
                "website",
                "email",
                "mobile_no",
                "job_title",
            ],
            "additionalProperties": False,
        },
    }


def _extract_function_args(response_json):
    for item in response_json.get("output", []) or []:
        if item.get("type") == "function_call" and item.get("name") == EXTRACT_TOOL_NAME:
            arguments = item.get("arguments")
            if isinstance(arguments, str):
                try:
                    return json.loads(arguments)
                except Exception:
                    return None
            if isinstance(arguments, dict):
                return arguments

    output_text = (response_json.get("output_text") or "").strip()
    if output_text:
        try:
            parsed = json.loads(output_text)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


def _normalize_extracted(data):
    keys = ["full_name", "first_name", "last_name", "website", "email", "mobile_no", "job_title"]
    out = {}

    for key in keys:
        val = data.get(key)
        if isinstance(val, str):
            val = val.strip()
        out[key] = val if val else None

    if out.get("email"):
        out["email"] = out["email"].lower()

    if out.get("mobile_no"):
        raw = str(out["mobile_no"])
        has_plus = raw.strip().startswith("+")
        digits = "".join(ch for ch in raw if ch.isdigit())
        out["mobile_no"] = f"+{digits}" if (has_plus and digits) else (digits or None)

    if out.get("website") and not out["website"].startswith(("http://", "https://")):
        out["website"] = f"https://{out['website']}"

    if not out.get("full_name"):
        parts = [out.get("first_name"), out.get("last_name")]
        merged = " ".join(p for p in parts if p)
        out["full_name"] = merged or None

    if out.get("full_name") and not out.get("first_name"):
        out["first_name"] = out["full_name"]

    return out


def _find_duplicate_lead(extracted: dict[str, Any]) -> str | None:
    if extracted.get("email"):
        existing = frappe.db.get_value("CRM Lead", {"email": extracted["email"]}, "name")
        if existing:
            return existing

    if extracted.get("mobile_no"):
        existing = frappe.db.get_value("CRM Lead", {"mobile_no": extracted["mobile_no"]}, "name")
        if existing:
            return existing

    return None


def _has_field(doctype, fieldname):
    return frappe.get_meta(doctype).has_field(fieldname)


def _insert_crm_lead(extracted, owner_user=None):
    doc = {"doctype": "CRM Lead"}

    first_name = extracted.get("first_name") or extracted.get("full_name") or "Business Card Lead"
    doc["first_name"] = first_name

    if extracted.get("last_name") and _has_field("CRM Lead", "last_name"):
        doc["last_name"] = extracted["last_name"]

    if extracted.get("full_name") and _has_field("CRM Lead", "lead_name"):
        doc["lead_name"] = extracted["full_name"]

    for field in ("email", "mobile_no", "website", "job_title"):
        if extracted.get(field) and _has_field("CRM Lead", field):
            doc[field] = extracted[field]

    if _has_field("CRM Lead", "source") and frappe.db.exists("CRM Lead Source", "Application"):
        doc["source"] = "Application"

    lead = frappe.get_doc(doc)

    lead_owner = owner_user or frappe.session.user
    if lead_owner and lead_owner != "Guest" and _has_field("CRM Lead", "lead_owner"):
        lead.lead_owner = lead_owner

    lead.insert(ignore_permissions=True)
    return lead


def _rename_and_move_business_card(file_doc, first_name: str | None):
    first_name = (first_name or "").strip().lower()
    if not first_name:
        return

    safe = re.sub(r"[^a-z0-9]+", "-", first_name).strip("-")
    if not safe:
        return

    _, ext = os.path.splitext(file_doc.file_name or "")
    ext = (ext or ".jpg").lower()
    new_name = f"{safe}{ext}"

    # keep file inside private/files/business-cards
    target_dir = frappe.get_site_path("private", "files", "business-cards")
    os.makedirs(target_dir, exist_ok=True)

    old_url = file_doc.file_url or f"/private/files/{file_doc.file_name}"
    old_abs = frappe.get_site_path(old_url.lstrip("/"))
    new_abs = os.path.join(target_dir, new_name)

    # avoid overwrite
    i = 1
    while os.path.exists(new_abs):
        new_name = f"{safe}-{i}{ext}"
        new_abs = os.path.join(target_dir, new_name)
        i += 1

    if os.path.exists(old_abs):
        os.replace(old_abs, new_abs)

    file_doc.file_name = new_name
    file_doc.file_url = f"/private/files/business-cards/{new_name}"
    file_doc.save(ignore_permissions=True)


def _save_business_card_file(image_bytes: bytes, filename: str | None, request_id: str):
    original_name = os.path.basename(filename or f"business-card-{request_id}.jpg")
    root, ext = os.path.splitext(original_name)

    safe_root = re.sub(r"[^A-Za-z0-9._-]+", "-", root).strip("-_.")
    if not safe_root:
        safe_root = f"business-card-{request_id}"

    if not ext:
        ext = ".jpg"
    ext = ext.lower()

    final_name = f"{safe_root}-{request_id}{ext}"

    file_doc = frappe.new_doc("File")
    file_doc.file_name = final_name
    file_doc.content = image_bytes
    file_doc.is_private = 1
    file_doc.folder = "Home/Attachments"
    file_doc.insert(ignore_permissions=True)
    return file_doc


def _attach_business_card_to_lead(lead_name: str, file_doc):
    file_doc.attached_to_doctype = "CRM Lead"
    file_doc.attached_to_name = lead_name
    file_doc.attached_to_field = "custom_business_card"
    file_doc.save(ignore_permissions=True)

    if _has_field("CRM Lead", "custom_business_card"):
        frappe.db.set_value(
            "CRM Lead",
            lead_name,
            "custom_business_card",
            file_doc.file_url,
            update_modified=False,
        )
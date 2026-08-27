"""Post-send proof — sha256 attachments, hrefs from decoded MIME parts."""

from __future__ import annotations

import hashlib
import re
from email import message_from_bytes
from email import policy as email_policy
from typing import Any

from pigeon_mcp.attachments import ResolvedAttachment
from pigeon_mcp.gmail_client import (
    get_attachment_bytes,
    get_message,
    get_message_raw,
    walk_parts,
)

_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)
_GOOGLE_URL = "google.com/url"


def extract_hrefs_from_mime(raw_mime: bytes) -> list[str]:
    """Decode each text/html MIME part and collect hrefs (not from base64 wire)."""
    msg = message_from_bytes(raw_mime, policy=email_policy.default)
    hrefs: list[str] = []
    if msg.is_multipart():
        parts = msg.walk()
    else:
        parts = [msg]
    for part in parts:
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_content_type() != "text/html":
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        hrefs.extend(_HREF_RE.findall(text))
    return hrefs


async def verify_send_proof(
    access_token: str,
    message_id: str,
    source_attachments: list[ResolvedAttachment],
) -> dict[str, Any]:
    sent_meta = await get_message(access_token, message_id, fmt="full")
    raw_mime = await get_message_raw(access_token, message_id)
    hrefs = extract_hrefs_from_mime(raw_mime)

    sent_files: list[dict[str, Any]] = []
    ok = True
    reasons: list[str] = []

    if any(_GOOGLE_URL in h for h in hrefs):
        ok = False
        reasons.append("href contains google.com/url")

    by_name = {a.filename: a for a in source_attachments}
    payload = sent_meta.get("payload", {})
    for part in walk_parts(payload):
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        att_id = body.get("attachmentId")
        if not filename or not att_id:
            continue
        source = by_name.get(filename)
        if not source:
            continue
        data = await get_attachment_bytes(access_token, message_id, att_id)
        sent_sha = hashlib.sha256(data).hexdigest()
        source_sha = hashlib.sha256(source.data).hexdigest()
        size_ok = len(data) >= int(source.size * 0.9)
        sha_ok = sent_sha == source_sha
        sent_files.append({"filename": filename, "size": len(data), "sha256": sent_sha})
        if not sha_ok:
            ok = False
            reasons.append(f"sha256 mismatch for {filename}")
        elif not size_ok:
            ok = False
            reasons.append(f"size below 90% for {filename}")

    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    result = {
        "id": sent_meta.get("id"),
        "threadId": sent_meta.get("threadId"),
        "from": headers.get("from", ""),
        "sizeEstimate": sent_meta.get("sizeEstimate"),
        "attachments": sent_files,
        "hrefs": hrefs,
        "ok": ok,
    }
    if not ok:
        result["error"] = "; ".join(reasons)
    return result

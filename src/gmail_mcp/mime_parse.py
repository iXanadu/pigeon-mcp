"""Decode Gmail message payloads to plain/HTML bodies."""

from __future__ import annotations

import base64
import re

from gmail_mcp.gmail_client import walk_parts

_TAG_RE = re.compile(r"<[^>]+>")


def _decode_part_data(data: str) -> str:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8", errors="replace")


def extract_plain_body(payload: dict) -> str:
    for part in walk_parts(payload):
        if part.get("mimeType") == "text/plain":
            data = (part.get("body") or {}).get("data")
            if data:
                return _decode_part_data(data).strip()
    for part in walk_parts(payload):
        if part.get("mimeType") == "text/html":
            data = (part.get("body") or {}).get("data")
            if data:
                html = _decode_part_data(data)
                return _TAG_RE.sub(" ", html).strip()
    return ""


def extract_html_body(payload: dict) -> str:
    for part in walk_parts(payload):
        if part.get("mimeType") == "text/html":
            data = (part.get("body") or {}).get("data")
            if data:
                return _decode_part_data(data).strip()
    return ""


def list_attachment_parts(payload: dict) -> list[dict]:
    out: list[dict] = []
    for part in walk_parts(payload):
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        if filename and body.get("attachmentId"):
            out.append(
                {
                    "filename": filename,
                    "attachmentId": body["attachmentId"],
                    "size": body.get("size"),
                    "mimeType": part.get("mimeType"),
                }
            )
    return out

"""Gmail REST client helpers."""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
GMAIL_UPLOAD = "https://gmail.googleapis.com/upload/gmail/v1"


class GmailApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


async def _request(
    method: str,
    url: str,
    access_token: str,
    *,
    json_body: dict | None = None,
    content: bytes | None = None,
    headers: dict[str, str] | None = None,
    params: dict | list | None = None,
) -> dict | bytes:
    hdrs = {"Authorization": f"Bearer {access_token}"}
    if headers:
        hdrs.update(headers)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.request(
            method,
            url,
            headers=hdrs,
            json=json_body,
            content=content,
            params=params,
        )
        if r.status_code >= 400:
            raise GmailApiError(r.text[:500], r.status_code)
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.content


# Headers worth having on every message without fetching a body. X-Gm-Original-To
# is the real recipient behind a catch-all rewrite; Authentication-Results carries
# the dkim/dmarc verdicts.
DISPATCH_HEADERS = (
    "From",
    "To",
    "Cc",
    "Subject",
    "Date",
    "Message-ID",
    "Reply-To",
    "Delivered-To",
    "X-Gm-Original-To",
    "Authentication-Results",
)


def _format_params(fmt: str) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = [("format", fmt)]
    if fmt == "metadata":
        params.extend(("metadataHeaders", h) for h in DISPATCH_HEADERS)
    return params


async def get_message(access_token: str, message_id: str, fmt: str = "metadata") -> dict:
    result = await _request(
        "GET",
        f"{GMAIL_API}/users/me/messages/{message_id}",
        access_token,
        params=_format_params(fmt),
    )
    assert isinstance(result, dict)
    return result


async def list_messages(
    access_token: str,
    query: str,
    *,
    max_results: int = 25,
    page_token: str = "",
) -> dict:
    params: dict[str, Any] = {"q": query, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    result = await _request("GET", f"{GMAIL_API}/users/me/messages", access_token, params=params)
    assert isinstance(result, dict)
    return result


async def list_threads(
    access_token: str,
    query: str,
    *,
    max_results: int = 25,
    page_token: str = "",
) -> dict:
    params: dict[str, Any] = {"q": query, "maxResults": max_results}
    if page_token:
        params["pageToken"] = page_token
    result = await _request("GET", f"{GMAIL_API}/users/me/threads", access_token, params=params)
    assert isinstance(result, dict)
    return result


async def get_thread(access_token: str, thread_id: str, fmt: str = "full") -> dict:
    result = await _request(
        "GET",
        f"{GMAIL_API}/users/me/threads/{thread_id}",
        access_token,
        params=_format_params(fmt),
    )
    assert isinstance(result, dict)
    return result


async def modify_thread(
    access_token: str,
    thread_id: str,
    *,
    add_label_ids: list[str] | None = None,
    remove_label_ids: list[str] | None = None,
) -> dict:
    body: dict[str, list[str]] = {}
    if add_label_ids:
        body["addLabelIds"] = add_label_ids
    if remove_label_ids:
        body["removeLabelIds"] = remove_label_ids
    result = await _request(
        "POST",
        f"{GMAIL_API}/users/me/threads/{thread_id}/modify",
        access_token,
        json_body=body,
    )
    assert isinstance(result, dict)
    return result


async def list_labels(access_token: str) -> dict:
    result = await _request("GET", f"{GMAIL_API}/users/me/labels", access_token)
    assert isinstance(result, dict)
    return result


async def create_label(access_token: str, name: str) -> dict:
    result = await _request(
        "POST",
        f"{GMAIL_API}/users/me/labels",
        access_token,
        json_body={
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show",
        },
    )
    assert isinstance(result, dict)
    return result


async def trash_thread(access_token: str, thread_id: str) -> dict:
    result = await _request(
        "POST",
        f"{GMAIL_API}/users/me/threads/{thread_id}/trash",
        access_token,
    )
    assert isinstance(result, dict)
    return result


async def untrash_thread(access_token: str, thread_id: str) -> dict:
    result = await _request(
        "POST",
        f"{GMAIL_API}/users/me/threads/{thread_id}/untrash",
        access_token,
    )
    assert isinstance(result, dict)
    return result


async def create_draft(
    access_token: str,
    mime_bytes: bytes,
    *,
    thread_id: str | None = None,
) -> dict:
    message: dict[str, Any] = {"raw": encode_raw_message(mime_bytes)}
    if thread_id:
        message["threadId"] = thread_id
    result = await _request(
        "POST",
        f"{GMAIL_API}/users/me/drafts",
        access_token,
        json_body={"message": message},
    )
    assert isinstance(result, dict)
    return result


async def send_draft(access_token: str, draft_id: str) -> dict:
    result = await _request(
        "POST",
        f"{GMAIL_API}/users/me/drafts/send",
        access_token,
        json_body={"id": draft_id},
    )
    assert isinstance(result, dict)
    return result


async def list_send_as(access_token: str) -> dict:
    result = await _request("GET", f"{GMAIL_API}/users/me/settings/sendAs", access_token)
    assert isinstance(result, dict)
    return result


async def get_send_as(access_token: str, email: str) -> dict:
    return await _request(
        "GET",
        f"{GMAIL_API}/users/me/settings/sendAs/{email}",
        access_token,
    )


def encode_raw_message(mime_bytes: bytes) -> str:
    return base64.urlsafe_b64encode(mime_bytes).decode().rstrip("=")


async def send_raw_mime(
    access_token: str,
    mime_bytes: bytes,
    *,
    thread_id: str | None = None,
) -> dict:
    """Upload RFC822 via Gmail multipart media upload."""
    metadata: dict[str, Any] = {}
    if thread_id:
        metadata["threadId"] = thread_id

    boundary = "gmcp_boundary"
    parts: list[bytes] = []
    meta_json = json.dumps(metadata).encode("utf-8")
    parts.append(
        f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
        + meta_json
        + b"\r\n"
    )
    parts.append(
        f"--{boundary}\r\nContent-Type: message/rfc822\r\n\r\n".encode()
        + mime_bytes
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    headers = {
        "Content-Type": f'multipart/related; boundary="{boundary}"',
    }
    result = await _request(
        "POST",
        f"{GMAIL_UPLOAD}/users/me/messages/send",
        access_token,
        content=body,
        headers=headers,
        params={"uploadType": "multipart"},
    )
    assert isinstance(result, dict)
    return result


def decode_raw_message(raw_b64: str) -> bytes:
    padded = raw_b64 + "=" * (-len(raw_b64) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


async def get_message_raw(access_token: str, message_id: str) -> bytes:
    data = await get_message(access_token, message_id, fmt="raw")
    return decode_raw_message(data["raw"])


async def get_attachment_bytes(access_token: str, message_id: str, attachment_id: str) -> bytes:
    data = await _request(
        "GET",
        f"{GMAIL_API}/users/me/messages/{message_id}/attachments/{attachment_id}",
        access_token,
    )
    assert isinstance(data, dict)
    return decode_raw_message(data["data"])


def parse_message_headers(message: dict) -> dict[str, str]:
    headers: dict[str, str] = {}
    for h in message.get("payload", {}).get("headers", []):
        name = h.get("name", "").lower()
        if name:
            headers[name] = h.get("value", "")
    return headers


def walk_parts(payload: dict) -> list[dict]:
    parts = [payload]
    for part in payload.get("parts") or []:
        parts.extend(walk_parts(part))
    return parts

"""Read and organise — search, threads, labels, drafts."""

from __future__ import annotations

import json
from typing import Any

from pigeon_mcp.attachments import resolve_attachments, resolve_download_path
from pigeon_mcp.config import settings
from pigeon_mcp.gmail_client import (
    get_attachment_bytes,
    get_message,
    get_thread,
    list_labels,
    list_threads,
    modify_thread,
    send_draft,
    trash_thread,
    untrash_thread,
    create_draft,
    create_label,
    parse_message_headers,
)
from pigeon_mcp.mail import _idempotency_store, _live_signature, _strip_html
from pigeon_mcp.mime_builder import build_mime
from pigeon_mcp.mime_parse import extract_html_body, extract_plain_body, list_attachment_parts
from pigeon_mcp.proof import verify_send_proof
from pigeon_mcp.session import access_token_for


def format_result(result: Any) -> str:
    return json.dumps(result, indent=2)


def _summarize_message(msg: dict, *, detail: str = "plain") -> dict[str, Any]:
    headers = parse_message_headers(msg)
    out: dict[str, Any] = {
        "id": msg.get("id"),
        "threadId": msg.get("threadId"),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "subject": headers.get("subject", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "labelIds": msg.get("labelIds", []),
    }
    payload = msg.get("payload") or {}
    if detail == "full":
        out["body"] = extract_plain_body(payload)
        out["htmlBody"] = extract_html_body(payload)
        out["attachments"] = list_attachment_parts(payload)
    elif detail == "plain":
        out["body"] = extract_plain_body(payload)
    # detail == "metadata" — headers + snippet only
    return out


async def _resolve_labels(access_token: str, labels_csv: str) -> list[str]:
    if not labels_csv.strip():
        return []
    data = await list_labels(access_token)
    by_name = {label["name"].lower(): label["id"] for label in data.get("labels", [])}
    by_id = {label["id"]: label["id"] for label in data.get("labels", [])}
    ids: list[str] = []
    for raw in labels_csv.split(","):
        name = raw.strip()
        if not name:
            continue
        if name in by_id:
            ids.append(by_id[name])
        elif name.lower() in by_name:
            ids.append(by_name[name.lower()])
        else:
            raise ValueError(f"Unknown label: {name}")
    return ids


async def search(
    account: str,
    query: str,
    max_results: int = 25,
    page_token: str = "",
) -> dict[str, Any]:
    token = await access_token_for(account)
    listing = await list_threads(
        token, query, max_results=max(1, min(max_results, 100)), page_token=page_token
    )
    threads = [
        {
            "id": t.get("id"),
            "snippet": t.get("snippet", ""),
            "historyId": t.get("historyId"),
        }
        for t in listing.get("threads", [])
    ]
    return {
        "account": account,
        "query": query,
        "threads": threads,
        "nextPageToken": listing.get("nextPageToken", ""),
    }


async def get_thread_messages(account: str, thread_id: str, format: str = "plain") -> dict[str, Any]:
    token = await access_token_for(account)
    detail = "full" if format == "full" else "plain"
    thread = await get_thread(token, thread_id, fmt="full")
    messages = [
        _summarize_message(m, detail=detail)
        for m in thread.get("messages", [])
    ]
    return {"account": account, "threadId": thread_id, "messages": messages}


async def get_message_detail(account: str, message_id: str, format: str = "plain") -> dict[str, Any]:
    token = await access_token_for(account)
    detail = "full" if format == "full" else "plain"
    msg = await get_message(token, message_id, fmt="full")
    return {"account": account, **_summarize_message(msg, detail=detail)}


async def get_attachment_file(
    account: str,
    message_id: str,
    attachment_id: str,
    output_path: str,
) -> dict[str, Any]:
    token = await access_token_for(account)
    path = resolve_download_path(settings.download_root, output_path)
    data = await get_attachment_bytes(token, message_id, attachment_id)
    path.write_bytes(data)
    return {"path": str(path), "size": len(data)}


async def labels_list(account: str) -> dict[str, Any]:
    token = await access_token_for(account)
    data = await list_labels(token)
    labels = [
        {"id": l["id"], "name": l["name"], "type": l.get("type", "")}
        for l in data.get("labels", [])
    ]
    return {"account": account, "labels": labels}


async def labels_create(account: str, name: str) -> dict[str, Any]:
    token = await access_token_for(account)
    label = await create_label(token, name)
    return {"account": account, "id": label["id"], "name": label["name"]}


async def label(account: str, thread_id: str, labels: str) -> dict[str, Any]:
    token = await access_token_for(account)
    ids = await _resolve_labels(token, labels)
    result = await modify_thread(token, thread_id, add_label_ids=ids)
    return {"account": account, "threadId": thread_id, "labelIds": result.get("labelIds", [])}


async def unlabel(account: str, thread_id: str, labels: str) -> dict[str, Any]:
    token = await access_token_for(account)
    ids = await _resolve_labels(token, labels)
    result = await modify_thread(token, thread_id, remove_label_ids=ids)
    return {"account": account, "threadId": thread_id, "labelIds": result.get("labelIds", [])}


async def archive(account: str, thread_id: str) -> dict[str, Any]:
    token = await access_token_for(account)
    result = await modify_thread(token, thread_id, remove_label_ids=["INBOX"])
    return {"account": account, "threadId": thread_id, "labelIds": result.get("labelIds", [])}


async def trash(account: str, thread_id: str) -> dict[str, Any]:
    token = await access_token_for(account)
    result = await trash_thread(token, thread_id)
    return {"account": account, "threadId": thread_id, "labelIds": result.get("labelIds", [])}


async def untrash(account: str, thread_id: str) -> dict[str, Any]:
    token = await access_token_for(account)
    result = await untrash_thread(token, thread_id)
    return {"account": account, "threadId": thread_id, "labelIds": result.get("labelIds", [])}


async def draft_create(
    account: str,
    to: str,
    subject: str,
    body: str = "",
    html_body: str = "",
    attachments: list[dict] | None = None,
    footer: str = "",
    cc: str = "",
    thread_id: str = "",
) -> dict[str, Any]:
    resolved = resolve_attachments(settings.outbox_root, attachments)
    token = await access_token_for(account)
    sig_html, sig_plain = await _live_signature(token, account)
    plain_sig = _strip_html(sig_plain or sig_html)
    to_list = [a.strip() for a in to.split(",") if a.strip()]
    cc_list = [a.strip() for a in cc.split(",") if a.strip()] if cc else None
    mime_bytes = build_mime(
        from_email=account,
        to=to_list,
        subject=subject,
        body=body,
        html_body=html_body,
        attachments=resolved,
        signature_html=sig_html,
        signature_plain=plain_sig,
        footer=footer,
        cc=cc_list,
    )
    draft = await create_draft(token, mime_bytes, thread_id=thread_id or None)
    return {
        "account": account,
        "draftId": draft.get("id"),
        "messageId": (draft.get("message") or {}).get("id"),
        "threadId": (draft.get("message") or {}).get("threadId"),
    }


async def draft_send(account: str, draft_id: str, idempotency_key: str) -> dict[str, Any]:
    if not idempotency_key:
        raise ValueError("idempotency_key is required")
    idem = _idempotency_store()
    cached = idem.get(account, idempotency_key)
    if cached:
        return cached

    token = await access_token_for(account)
    sent = await send_draft(token, draft_id)
    message_id = sent["id"]
    proof = await verify_send_proof(token, message_id, [])
    if not proof.get("ok"):
        raise RuntimeError(f"Send proof failed: {proof.get('error', proof)}")

    result = {"account": account, "draftId": draft_id, "idempotency_key": idempotency_key, **proof}
    idem.put(account, idempotency_key, result)
    return result

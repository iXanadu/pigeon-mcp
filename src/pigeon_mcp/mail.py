"""Send, reply, forward — server-built MIME with proof."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from pigeon_mcp.attachments import MAX_TOTAL_BYTES, ResolvedAttachment, resolve_attachments
from pigeon_mcp.config import settings
from pigeon_mcp.gmail_client import (
    decode_raw_message,
    get_attachment_bytes,
    get_message,
    parse_message_headers,
    send_raw_mime,
    walk_parts,
)
from pigeon_mcp.google_oauth import ensure_fresh_token
from pigeon_mcp.idempotency import IdempotencyStore
from pigeon_mcp.identities import resolve_sender
from pigeon_mcp.mime_builder import build_mime
from pigeon_mcp.mime_parse import extract_html_body, extract_plain_body
from pigeon_mcp.oauth_constants import STATUS_NEEDS_AUTH
from pigeon_mcp.proof import verify_send_proof
from pigeon_mcp.token_store import TokenStore


def _idempotency_store() -> IdempotencyStore:
    return IdempotencyStore(Path(settings.tokens_dir).parent / "idempotency.json")


def _token_store() -> TokenStore:
    return TokenStore(settings.tokens_dir)


async def _access_token_for(account: str) -> str:
    store = _token_store()
    token = await ensure_fresh_token(store, account)
    if not token:
        raise ValueError(f"Unknown account: {account}")
    if token.status == STATUS_NEEDS_AUTH:
        raise ValueError(f"Account {account} needs re-consent (needs_auth)")
    if token.email.lower() != account.lower():
        raise ValueError(f"Account mismatch: expected {account}, have {token.email}")
    if not token.access_token:
        raise ValueError(f"No access token for {account}")
    return token.access_token


async def _deliver(
    *,
    account: str,
    idempotency_key: str,
    mime_bytes: bytes,
    thread_id: str | None,
    attachments: list,
) -> dict[str, Any]:
    if not idempotency_key:
        raise ValueError("idempotency_key is required")

    idem = _idempotency_store()
    cached = idem.get(account, idempotency_key)
    if cached:
        return cached

    access_token = await _access_token_for(account)
    sent = await send_raw_mime(access_token, mime_bytes, thread_id=thread_id)
    message_id = sent["id"]
    proof = await verify_send_proof(access_token, message_id, attachments)
    if not proof.get("ok"):
        raise RuntimeError(f"Send proof failed: {proof.get('error', proof)}")

    result = {"account": account, "idempotency_key": idempotency_key, **proof}
    idem.put(account, idempotency_key, result)
    return result


async def send(
    *,
    account: str,
    to: str,
    subject: str,
    idempotency_key: str,
    body: str = "",
    html_body: str = "",
    attachments: list[dict] | None = None,
    footer: str = "",
    cc: str = "",
    from_identity: str = "",
) -> dict[str, Any]:
    resolved = resolve_attachments(settings.outbox_root, attachments)
    access_token = await _access_token_for(account)
    sender = await resolve_sender(access_token, account, from_identity)
    sig_html = sender.signature_html
    plain_sig = _strip_html(sig_html)
    to_list = [a.strip() for a in to.split(",") if a.strip()]
    cc_list = [a.strip() for a in cc.split(",") if a.strip()] if cc else None
    mime_bytes = build_mime(
        from_email=sender.email,
        from_name=sender.display_name,
        reply_to=sender.reply_to,
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
    return await _deliver(
        account=account,
        idempotency_key=idempotency_key,
        mime_bytes=mime_bytes,
        thread_id=None,
        attachments=resolved,
    )


async def reply(
    *,
    account: str,
    message_id: str,
    idempotency_key: str,
    body: str = "",
    html_body: str = "",
    attachments: list[dict] | None = None,
    footer: str = "",
    subject: str = "",
    from_identity: str = "",
) -> dict[str, Any]:
    resolved = resolve_attachments(settings.outbox_root, attachments)
    access_token = await _access_token_for(account)
    original = await get_message(access_token, message_id, fmt="metadata")
    headers = parse_message_headers(original)
    thread_id = original.get("threadId")
    in_reply_to = headers.get("message-id", "")
    references = headers.get("references", "")
    if in_reply_to and in_reply_to not in references:
        references = f"{references} {in_reply_to}".strip()
    subj = subject or headers.get("subject", "")
    if subj and not subj.lower().startswith("re:"):
        subj = f"Re: {subj}"

    sender = await resolve_sender(access_token, account, from_identity)
    sig_html = sender.signature_html
    plain_sig = _strip_html(sig_html)
    to_raw = headers.get("reply-to") or headers.get("from", "")
    to_list = _parse_addresses(to_raw)
    mime_bytes = build_mime(
        from_email=sender.email,
        from_name=sender.display_name,
        reply_to=sender.reply_to,
        to=to_list,
        subject=subj,
        body=body,
        html_body=html_body,
        attachments=resolved,
        signature_html=sig_html,
        signature_plain=plain_sig,
        footer=footer,
        in_reply_to=in_reply_to or None,
        references=references or None,
    )
    return await _deliver(
        account=account,
        idempotency_key=idempotency_key,
        mime_bytes=mime_bytes,
        thread_id=thread_id,
        attachments=resolved,
    )


async def forward(
    *,
    account: str,
    message_id: str,
    to: str,
    idempotency_key: str,
    body: str = "",
    html_body: str = "",
    attachments: list[dict] | None = None,
    footer: str = "",
    subject: str = "",
    from_identity: str = "",
    include_original_attachments: bool = True,
) -> dict[str, Any]:
    """Forward the original message: its quoted body and its attachments travel with it."""
    resolved = resolve_attachments(settings.outbox_root, attachments)
    access_token = await _access_token_for(account)
    original = await get_message(access_token, message_id, fmt="full")
    headers = parse_message_headers(original)
    payload = original.get("payload") or {}
    thread_id = original.get("threadId")
    in_reply_to = headers.get("message-id", "")
    references = headers.get("references", "")
    if in_reply_to and in_reply_to not in references:
        references = f"{references} {in_reply_to}".strip()

    if include_original_attachments:
        resolved = await _original_attachments(access_token, message_id, payload) + resolved
        total = sum(a.size for a in resolved)
        if total > MAX_TOTAL_BYTES:
            raise ValueError(
                f"forward with original attachments is {total} bytes, over the "
                f"{MAX_TOTAL_BYTES}-byte Gmail cap"
            )

    subj = subject or headers.get("subject", "")
    if subj and not subj.lower().startswith("fwd:"):
        subj = f"Fwd: {subj}"

    sender = await resolve_sender(access_token, account, from_identity)
    sig_html = sender.signature_html
    plain_sig = _strip_html(sig_html)

    # The note and signature sit above the forwarded block, as a mail client puts them.
    note_plain = _join_blocks(body or _strip_html(html_body), plain_sig, "\n\n")
    note_html = _join_blocks(html_body or _plain_to_html(body), sig_html, "<br><br>")
    orig_plain = extract_plain_body(payload)
    orig_html = extract_html_body(payload) or _plain_to_html(orig_plain)
    fwd_plain = _join_blocks(
        note_plain, _forward_header_plain(headers) + "\n\n" + orig_plain, "\n\n"
    )
    fwd_html = _join_blocks(
        note_html,
        f"<div>{_forward_header_html(headers)}<br><br>{orig_html}</div>",
        "<br><br>",
    )

    to_list = [a.strip() for a in to.split(",") if a.strip()]
    mime_bytes = build_mime(
        from_email=sender.email,
        from_name=sender.display_name,
        reply_to=sender.reply_to,
        to=to_list,
        subject=subj,
        body=fwd_plain,
        html_body=fwd_html,
        attachments=resolved,
        footer=footer,
        in_reply_to=in_reply_to or None,
        references=references or None,
    )
    return await _deliver(
        account=account,
        idempotency_key=idempotency_key,
        mime_bytes=mime_bytes,
        thread_id=thread_id,
        attachments=resolved,
    )


async def _original_attachments(
    access_token: str, message_id: str, payload: dict
) -> list[ResolvedAttachment]:
    out: list[ResolvedAttachment] = []
    for part in walk_parts(payload):
        filename = part.get("filename") or ""
        body = part.get("body") or {}
        if not filename:
            continue
        if body.get("attachmentId"):
            data = await get_attachment_bytes(access_token, message_id, body["attachmentId"])
        elif body.get("data"):
            # Gmail inlines small parts in the payload instead of giving an attachmentId.
            data = decode_raw_message(body["data"])
        else:
            continue
        out.append(
            ResolvedAttachment(
                path=Path(filename),
                filename=filename,
                mime_type=part.get("mimeType") or "application/octet-stream",
                size=len(data),
                data=data,
            )
        )
    return out


_FWD_FIELDS = (("From", "from"), ("Date", "date"), ("Subject", "subject"), ("To", "to"), ("Cc", "cc"))


def _forward_header_plain(headers: dict[str, str]) -> str:
    lines = ["---------- Forwarded message ---------"]
    lines += [f"{label}: {headers[key]}" for label, key in _FWD_FIELDS if headers.get(key)]
    return "\n".join(lines)


def _forward_header_html(headers: dict[str, str]) -> str:
    lines = ["---------- Forwarded message ---------"]
    lines += [
        f"{label}: {html.escape(headers[key])}" for label, key in _FWD_FIELDS if headers.get(key)
    ]
    return "<br>".join(lines)


def _plain_to_html(text: str) -> str:
    return html.escape(text).replace("\n", "<br>") if text else ""


def _join_blocks(first: str, second: str, sep: str) -> str:
    return sep.join(b for b in (first.strip(), second.strip()) if b)


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_addresses(header: str) -> list[str]:
    # Minimal: extract emails from From/Reply-To
    import re

    return re.findall(r"[\w.+-]+@[\w.-]+\.\w+", header) or [header.strip()]


def format_result(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2)

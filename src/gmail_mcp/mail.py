"""Send, reply, forward — server-built MIME with proof."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gmail_mcp.attachments import resolve_attachments
from gmail_mcp.config import settings
from gmail_mcp.gmail_client import (
    GmailApiError,
    get_message,
    get_send_as,
    parse_message_headers,
    send_raw_mime,
)
from gmail_mcp.google_oauth import ensure_fresh_token
from gmail_mcp.idempotency import IdempotencyStore
from gmail_mcp.mime_builder import build_mime
from gmail_mcp.oauth_constants import STATUS_NEEDS_AUTH
from gmail_mcp.proof import verify_send_proof
from gmail_mcp.token_store import TokenStore


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


async def _live_signature(access_token: str, account: str) -> tuple[str, str]:
    try:
        send_as = await get_send_as(access_token, account)
    except GmailApiError:
        return "", ""
    return send_as.get("signature", "") or "", ""


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
) -> dict[str, Any]:
    resolved = resolve_attachments(settings.outbox_root, attachments)
    access_token = await _access_token_for(account)
    sig_html, sig_plain = await _live_signature(access_token, account)
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

    sig_html, sig_plain = await _live_signature(access_token, account)
    plain_sig = _strip_html(sig_plain or sig_html)
    to_raw = headers.get("reply-to") or headers.get("from", "")
    to_list = _parse_addresses(to_raw)
    mime_bytes = build_mime(
        from_email=account,
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
    if subj and not subj.lower().startswith("fwd:"):
        subj = f"Fwd: {subj}"

    sig_html, sig_plain = await _live_signature(access_token, account)
    plain_sig = _strip_html(sig_plain or sig_html)
    to_list = [a.strip() for a in to.split(",") if a.strip()]
    mime_bytes = build_mime(
        from_email=account,
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


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", "", text).strip()


def _parse_addresses(header: str) -> list[str]:
    # Minimal: extract emails from From/Reply-To
    import re

    return re.findall(r"[\w.+-]+@[\w.-]+\.\w+", header) or [header.strip()]


def format_result(result: dict[str, Any]) -> str:
    return json.dumps(result, indent=2)

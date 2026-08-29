"""Send-as identities — the registry of addresses an account may send from.

Gmail's ``sendAs`` list is authoritative: it returns exactly the identities the
mailbox will accept on ``From``, with display names and verification state.
Nothing here keeps a separate roster. Validation happens in the handler, not in
a prompt — an unknown ``from_identity`` is rejected before any MIME is built.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pigeon_mcp.gmail_client import GmailApiError, get_send_as, list_send_as
from pigeon_mcp.session import access_token_for

VERIFIED = "accepted"


@dataclass(frozen=True)
class SenderIdentity:
    email: str
    display_name: str = ""
    reply_to: str | None = None
    signature_html: str = ""


def _is_usable(entry: dict[str, Any]) -> bool:
    # The primary address carries no verificationStatus; aliases must be accepted.
    status = entry.get("verificationStatus")
    return status is None or status == VERIFIED


def _summarize(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "email": entry.get("sendAsEmail", ""),
        "displayName": entry.get("displayName", "") or "",
        "isDefault": bool(entry.get("isDefault", False)),
        "isPrimary": bool(entry.get("isPrimary", False)),
        "replyTo": entry.get("replyToAddress", "") or "",
        "hasSignature": bool(entry.get("signature")),
    }


async def list_identities(account: str) -> dict[str, Any]:
    """Verified send-as identities for a connected account (sendAs.list, accepted only)."""
    token = await access_token_for(account)
    data = await list_send_as(token)
    rows = [_summarize(e) for e in data.get("sendAs", []) if _is_usable(e)]
    return {"account": account, "identities": rows}


async def resolve_sender(access_token: str, account: str, from_identity: str = "") -> SenderIdentity:
    """Pick the identity a message goes out as.

    Empty ``from_identity`` keeps the historical behaviour: bare account address,
    live signature for that address. Otherwise the address must be a verified
    send-as entry on this mailbox; the entry supplies display name, Reply-To and
    signature.
    """
    wanted = (from_identity or "").strip()
    if not wanted:
        try:
            entry = await get_send_as(access_token, account)
        except GmailApiError:
            entry = {}
        return SenderIdentity(email=account, signature_html=entry.get("signature", "") or "")

    data = await list_send_as(access_token)
    usable = [e for e in data.get("sendAs", []) if _is_usable(e)]
    for entry in usable:
        if entry.get("sendAsEmail", "").lower() == wanted.lower():
            email = entry["sendAsEmail"]
            return SenderIdentity(
                email=email,
                display_name=entry.get("displayName", "") or "",
                reply_to=entry.get("replyToAddress") or email,
                signature_html=entry.get("signature", "") or "",
            )
    allowed = ", ".join(sorted(e.get("sendAsEmail", "") for e in usable)) or "(none)"
    raise ValueError(
        f"from_identity {wanted!r} is not a verified send-as identity on {account}. "
        f"Allowed: {allowed}. Add it in Gmail settings (Accounts → Send mail as) first."
    )

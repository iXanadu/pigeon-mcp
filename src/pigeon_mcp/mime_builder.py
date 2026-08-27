"""Build RFC822 MIME on the server — no link rewriting."""

from __future__ import annotations

import re
from email import encoders, policy
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid

from pigeon_mcp.attachments import ResolvedAttachment

_MSGID_DOMAIN = "pigeon-mcp.local"
_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_plain(html: str) -> str:
    text = _TAG_RE.sub("", html)
    return text.strip()


def _append_block(existing: str, block: str, html: bool) -> str:
    block = block.strip()
    if not block:
        return existing
    if not existing:
        return block
    if html:
        return f"{existing}<br><br>{block}"
    return f"{existing}\n\n{block}"


def _attach_bodies(
    container: MIMEMultipart,
    plain: str,
    html: str,
) -> None:
    if plain and html:
        container.attach(MIMEText(plain, "plain", "utf-8"))
        container.attach(MIMEText(html, "html", "utf-8"))
    elif plain:
        container.attach(MIMEText(plain, "plain", "utf-8"))
    elif html:
        container.attach(MIMEText(html, "html", "utf-8"))


def build_mime(
    *,
    from_email: str,
    to: list[str],
    subject: str,
    body: str = "",
    html_body: str = "",
    attachments: list[ResolvedAttachment] | None = None,
    signature_html: str = "",
    signature_plain: str = "",
    footer: str = "",
    in_reply_to: str | None = None,
    references: str | None = None,
    cc: list[str] | None = None,
) -> bytes:
    attachments = attachments or []
    has_attachments = bool(attachments)

    plain = body
    html = html_body

    if signature_plain:
        plain = _append_block(plain, signature_plain, html=False)
    if signature_html:
        html = _append_block(html, signature_html, html=True)
    if footer:
        plain = _append_block(plain, footer, html=False)
        html = _append_block(html, footer, html=True)

    if html and not plain:
        plain = _html_to_plain(html)

    if has_attachments:
        root: MIMEMultipart | MIMEText = MIMEMultipart("mixed")
    elif plain and html:
        root = MIMEMultipart("alternative")
    elif plain:
        root = MIMEText(plain, "plain", "utf-8")
    elif html:
        root = MIMEMultipart("alternative")
    else:
        root = MIMEText("", "plain", "utf-8")

    root["From"] = formataddr(("", from_email))
    root["To"] = ", ".join(to)
    if cc:
        root["Cc"] = ", ".join(cc)
    root["Subject"] = subject
    root["Date"] = formatdate(localtime=True)
    root["Message-ID"] = make_msgid(domain=_MSGID_DOMAIN)
    if in_reply_to:
        root["In-Reply-To"] = in_reply_to
    if references:
        root["References"] = references

    if has_attachments:
        assert isinstance(root, MIMEMultipart)
        alt = MIMEMultipart("alternative")
        _attach_bodies(alt, plain, html)
        root.attach(alt)
        for att in attachments:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(att.data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", "attachment", filename=att.filename)
            if att.mime_type != "application/octet-stream":
                part.set_type(att.mime_type)
            root.attach(part)
    elif isinstance(root, MIMEMultipart):
        _attach_bodies(root, plain, html)

    return root.as_bytes(policy=policy.SMTP)

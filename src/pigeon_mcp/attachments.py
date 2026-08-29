"""Attachment path validation — outbox root only, no inline content."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

MAX_TOTAL_BYTES = 25 * 1024 * 1024
FORBIDDEN_KEYS = frozenset({"content", "contentBase64", "content_base64"})
_CTRL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass
class ResolvedAttachment:
    path: Path
    filename: str
    mime_type: str
    size: int
    data: bytes


def _reject_inline_fields(item: dict) -> None:
    for key in FORBIDDEN_KEYS:
        if key in item:
            raise ValueError(f"attachments must use path only — rejected field {key!r}")


def sanitize_outbox_filename(name: str) -> str:
    """Basename only — preserve real display names; reject path tricks and controls.

    Spaces, parentheses, apostrophes, unicode stay. We do NOT collapse to
    [A-Za-z0-9._-] — that silently renames 'Q3 Report.docx' on send.

    Reject before Path.name can strip '../' into a harmless-looking basename.
    """
    raw = name.strip()
    if not raw or raw in {".", ".."}:
        raise ValueError("filename is required")
    if raw.startswith("."):
        raise ValueError("filename must not start with a dot")
    if "/" in raw or "\\" in raw or "\x00" in raw:
        raise ValueError("filename must be a bare basename")
    if ".." in raw:
        raise ValueError("filename must not contain ..")
    if _CTRL.search(raw):
        raise ValueError("filename contains control characters")
    if len(raw) > 200:
        raise ValueError("filename too long")
    base = Path(raw).name
    if base != raw:
        raise ValueError("filename must be a bare basename")
    return base


def stage_outbox_bytes(
    outbox_root: Path,
    *,
    filename: str,
    data: bytes,
    overwrite: bool = False,
) -> Path:
    """Write bytes under outbox_root. Returns the absolute path for send()."""
    if len(data) > MAX_TOTAL_BYTES:
        raise ValueError(f"file exceeds {MAX_TOTAL_BYTES} bytes (Gmail 25 MB cap)")
    root = outbox_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    safe = sanitize_outbox_filename(filename)
    dest = (root / safe).resolve()
    try:
        dest.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"filename escapes outbox root {root}") from exc
    if dest.exists() and not overwrite:
        dest = (root / f"{uuid.uuid4().hex[:8]}_{safe}").resolve()
        dest.relative_to(root)
    dest.write_bytes(data)
    return dest


def resolve_download_path(download_root: Path, output_path: str) -> Path:
    """Resolve output_path; must stay under download_root after symlink resolution.

    A relative output_path (the common case: just a filename) is anchored under
    download_root, never the process CWD — a bare "deed.pdf" must work from any
    working directory the service happens to run in.
    """
    root = download_root.expanduser().resolve()
    raw = Path(output_path).expanduser()
    if not raw.is_absolute():
        raw = root / raw
    path = raw.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"output_path must be under download root {root}: {path}"
        ) from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def resolve_attachments(outbox_root: Path, items: list[dict] | None) -> list[ResolvedAttachment]:
    if not items:
        return []
    root = outbox_root.expanduser().resolve()
    resolved: list[ResolvedAttachment] = []
    total = 0
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each attachment must be an object with path")
        _reject_inline_fields(item)
        raw_path = item.get("path")
        if not raw_path:
            raise ValueError("attachment.path is required")
        path = Path(raw_path).expanduser().resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"attachment path must be under outbox root {root}: {path}"
            ) from exc
        if not path.is_file():
            raise ValueError(f"attachment file not found: {path}")
        size = path.stat().st_size
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ValueError(f"attachments exceed {MAX_TOTAL_BYTES} bytes (Gmail 25 MB cap)")
        filename = item.get("filename") or path.name
        mime_type = item.get("mimeType") or item.get("mime_type") or "application/octet-stream"
        resolved.append(
            ResolvedAttachment(
                path=path,
                filename=filename,
                mime_type=mime_type,
                size=size,
                data=path.read_bytes(),
            )
        )
    return resolved

"""Attachment path validation — outbox root only, no inline content."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

MAX_TOTAL_BYTES = 25 * 1024 * 1024
FORBIDDEN_KEYS = frozenset({"content", "contentBase64", "content_base64"})


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


def resolve_download_path(download_root: Path, output_path: str) -> Path:
    """Resolve output_path; must stay under download_root after symlink resolution."""
    root = download_root.expanduser().resolve()
    path = Path(output_path).expanduser().resolve()
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

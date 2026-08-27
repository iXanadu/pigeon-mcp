"""Per-account OAuth token files — mode 0600, one JSON file per Gmail address."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gmail_mcp.oauth_constants import STATUS_ACTIVE, STATUS_NEEDS_AUTH

_EMAIL_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def _safe_name(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        raise ValueError(f"Not an email address: {email!r}")
    return f"{_EMAIL_SAFE.sub('_', local)}_at_{_EMAIL_SAFE.sub('_', domain)}.json"


@dataclass
class AccountToken:
    email: str
    refresh_token: str
    access_token: str = ""
    expires_at: str | None = None  # ISO8601 UTC
    scopes: str = ""
    status: str = STATUS_ACTIVE
    last_error: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AccountToken:
        return cls(
            email=data["email"],
            refresh_token=data.get("refresh_token", ""),
            access_token=data.get("access_token", ""),
            expires_at=data.get("expires_at"),
            scopes=data.get("scopes", ""),
            status=data.get("status", STATUS_ACTIVE),
            last_error=data.get("last_error", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TokenStore:
    def __init__(self, tokens_dir: Path) -> None:
        self.tokens_dir = tokens_dir.expanduser()

    def ensure_dir(self) -> None:
        self.tokens_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.tokens_dir, 0o700)

    def path_for(self, email: str) -> Path:
        return self.tokens_dir / _safe_name(email.lower())

    def list_emails(self) -> list[str]:
        if not self.tokens_dir.is_dir():
            return []
        emails: list[str] = []
        for path in sorted(self.tokens_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                email = data.get("email")
                if email:
                    emails.append(email)
            except (json.JSONDecodeError, OSError):
                continue
        return emails

    def load(self, email: str) -> AccountToken | None:
        path = self.path_for(email)
        if not path.is_file():
            return None
        try:
            return AccountToken.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def save(self, token: AccountToken) -> None:
        self.ensure_dir()
        path = self.path_for(token.email)
        path.write_text(json.dumps(token.to_dict(), indent=2) + "\n", encoding="utf-8")
        os.chmod(path, 0o600)

    def delete(self, email: str) -> bool:
        path = self.path_for(email)
        if path.is_file():
            path.unlink()
            return True
        return False

    def mark_needs_auth(self, email: str, error: str) -> None:
        token = self.load(email)
        if not token:
            return
        token.status = STATUS_NEEDS_AUTH
        token.last_error = error[:500]
        self.save(token)

    @staticmethod
    def expires_in_seconds(expires_at: str | None) -> float | None:
        if not expires_at:
            return None
        try:
            dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (dt - datetime.now(timezone.utc)).total_seconds()
        except ValueError:
            return None

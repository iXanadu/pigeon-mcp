"""Per-account OAuth token files — mode 0640, basename contains 'token' for backup classifiers."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pigeon_mcp.oauth_constants import STATUS_ACTIVE, STATUS_NEEDS_AUTH

_EMAIL_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")

# Directory traversable by the process group; files group-readable for host backups.
_DIR_MODE = 0o750
_FILE_MODE = 0o640


def _safe_email_slug(email: str) -> str:
    local, _, domain = email.partition("@")
    if not domain:
        raise ValueError(f"Not an email address: {email!r}")
    return f"{_EMAIL_SAFE.sub('_', local)}_at_{_EMAIL_SAFE.sub('_', domain)}"


def _safe_name(email: str) -> str:
    """Basename must include 'token' so backup tools that match filenames pick it up."""
    return f"gmail-token-{_safe_email_slug(email)}.json"


def _legacy_name(email: str) -> str:
    """Pre-cutover naming — still readable so existing Mac tokens migrate on next save."""
    return f"{_safe_email_slug(email)}.json"


@dataclass
class AccountToken:
    email: str
    refresh_token: str
    access_token: str = ""
    expires_at: str | None = None  # ISO8601 UTC
    scopes: str = ""
    status: str = STATUS_ACTIVE
    last_error: str = ""
    # OAuth client that minted the refresh token (Desktop vs Web). Empty on legacy files.
    client_id: str = ""

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
            client_id=data.get("client_id", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _durable(token: AccountToken) -> tuple[str, ...]:
    """Fields that belong on disk. Access tokens rotate ~hourly — rewriting them
    makes backup classifiers treat a cache write as a secret rotation."""
    return (
        token.email,
        token.refresh_token,
        token.scopes or "",
        token.status,
        token.last_error or "",
        token.client_id or "",
    )


def _disk_payload(token: AccountToken) -> dict[str, Any]:
    data = token.to_dict()
    data["access_token"] = ""
    data["expires_at"] = None
    return data


# Process-wide live access tokens. TokenStore is constructed per call, so this
# cannot live on the instance. Keyed by (tokens_dir, email).
_LIVE: dict[tuple[str, str], AccountToken] = {}


class TokenStore:
    def __init__(self, tokens_dir: Path) -> None:
        self.tokens_dir = tokens_dir.expanduser()

    def _live_key(self, email: str) -> tuple[str, str]:
        return (str(self.tokens_dir), email.lower())

    def ensure_dir(self) -> None:
        self.tokens_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.tokens_dir, _DIR_MODE)

    def path_for(self, email: str) -> Path:
        return self.tokens_dir / _safe_name(email.lower())

    def _legacy_path_for(self, email: str) -> Path:
        return self.tokens_dir / _legacy_name(email.lower())

    def list_emails(self) -> list[str]:
        if not self.tokens_dir.is_dir():
            return []
        emails: list[str] = []
        seen: set[str] = set()
        for path in sorted(self.tokens_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                email = data.get("email")
                if email and email not in seen:
                    seen.add(email)
                    emails.append(email)
            except (json.JSONDecodeError, OSError):
                continue
        return emails

    def load(self, email: str) -> AccountToken | None:
        key = self._live_key(email)
        cached = _LIVE.get(key)
        if cached is not None:
            return replace(cached)
        token = self._load_disk(email)
        if token is None:
            return None
        _LIVE[key] = replace(token)
        return replace(token)

    def _load_disk(self, email: str) -> AccountToken | None:
        for path in (self.path_for(email), self._legacy_path_for(email)):
            if not path.is_file():
                continue
            try:
                return AccountToken.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError, OSError):
                continue
        return None

    def save(self, token: AccountToken) -> None:
        _LIVE[self._live_key(token.email)] = replace(token)
        path = self.path_for(token.email)
        if path.is_file():
            try:
                existing = AccountToken.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError, OSError):
                existing = None
            if existing is not None and _durable(existing) == _durable(token):
                return
        self.ensure_dir()
        path.write_text(json.dumps(_disk_payload(token), indent=2) + "\n", encoding="utf-8")
        os.chmod(path, _FILE_MODE)
        legacy = self._legacy_path_for(token.email)
        if legacy != path and legacy.is_file():
            legacy.unlink()

    def delete(self, email: str) -> bool:
        _LIVE.pop(self._live_key(email), None)
        removed = False
        for path in (self.path_for(email), self._legacy_path_for(email)):
            if path.is_file():
                path.unlink()
                removed = True
        return removed

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

"""Idempotency store — idempotency_key → prior send result."""

from __future__ import annotations

import json
import os
from pathlib import Path


class IdempotencyStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser()

    def _load(self) -> dict:
        if not self.path.is_file():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.chmod(self.path, 0o600)

    def _key(self, account: str, idempotency_key: str) -> str:
        return f"{account.lower()}::{idempotency_key}"

    def get(self, account: str, idempotency_key: str) -> dict | None:
        return self._load().get(self._key(account, idempotency_key))

    def put(self, account: str, idempotency_key: str, result: dict) -> None:
        data = self._load()
        data[self._key(account, idempotency_key)] = result
        self._save(data)

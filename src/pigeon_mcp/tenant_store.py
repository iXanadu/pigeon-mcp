"""SQLite drawer for admin passkeys, named tenant bearers, grants, and audit."""

from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

TOKEN_PREFIX = "pgn_"
_ROOT_ID = "usr_root"
_GROKBOT = "grokbot"
_SETUP_TTL = timedelta(minutes=30)
_SESSION_TTL = timedelta(days=30)
_CHALLENGE_TTL = timedelta(minutes=5)


def sha256_secret(value: str) -> bytes:
    return hashlib.sha256(value.encode("utf-8")).digest()


def new_api_secret() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(10)}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Tenant:
    id: str
    name: str
    can_auth_start: bool
    grants: frozenset[str]

    def allows(self, account: str) -> bool:
        return account.lower() in self.grants


@dataclass(frozen=True)
class AdminSession:
    id: str
    user_id: str
    purpose: str  # setup | full


class TenantStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS app_user (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS passkey_credential (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES app_user(id),
                credential_id BLOB NOT NULL UNIQUE,
                public_key BLOB NOT NULL,
                sign_count INTEGER NOT NULL DEFAULT 0,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT
            );
            CREATE TABLE IF NOT EXISTS session (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES app_user(id),
                token_hash BLOB NOT NULL UNIQUE,
                purpose TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS setup_token (
                token_hash BLOB PRIMARY KEY,
                expires_at TEXT NOT NULL,
                used_at TEXT
            );
            CREATE TABLE IF NOT EXISTS tenant (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                token_hash BLOB NOT NULL UNIQUE,
                display_prefix TEXT NOT NULL,
                can_auth_start INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                last_used_at TEXT
            );
            CREATE TABLE IF NOT EXISTS account_grant (
                tenant_id TEXT NOT NULL REFERENCES tenant(id),
                account TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, account)
            );
            CREATE TABLE IF NOT EXISTS audit_event (
                id TEXT PRIMARY KEY,
                at TEXT NOT NULL,
                tenant_name TEXT NOT NULL,
                tool TEXT NOT NULL,
                account TEXT NOT NULL DEFAULT '',
                from_identity TEXT NOT NULL DEFAULT '',
                target_id TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS webauthn_challenge (
                challenge TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS audit_event_at ON audit_event(at DESC);
            """
        )
        self._conn.commit()

    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _fetchone(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def _fetchall(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

    def ensure_root(self) -> str:
        row = self._fetchone("SELECT id FROM app_user WHERE id = ?", (_ROOT_ID,))
        if row:
            return _ROOT_ID
        self._exec(
            "INSERT INTO app_user (id, created_at) VALUES (?, ?)",
            (_ROOT_ID, _now()),
        )
        return _ROOT_ID

    def has_passkey(self) -> bool:
        row = self._fetchone("SELECT 1 FROM passkey_credential LIMIT 1")
        return row is not None

    def passkey_count(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS n FROM passkey_credential")
        return int(row["n"]) if row else 0

    def create_setup_token(self) -> str:
        self.ensure_root()
        secret = secrets.token_urlsafe(24)
        expires = _iso(datetime.now(timezone.utc) + _SETUP_TTL)
        self._exec(
            "INSERT INTO setup_token (token_hash, expires_at) VALUES (?, ?)",
            (sha256_secret(secret), expires),
        )
        return secret

    def setup_token_ok(self, secret: str) -> bool:
        row = self._fetchone(
            "SELECT expires_at, used_at FROM setup_token WHERE token_hash = ?",
            (sha256_secret(secret),),
        )
        if not row or row["used_at"]:
            return False
        return row["expires_at"] >= _now()

    def consume_setup_token(self, secret: str) -> bool:
        if not self.setup_token_ok(secret):
            return False
        self._exec(
            "UPDATE setup_token SET used_at = ? WHERE token_hash = ?",
            (_now(), sha256_secret(secret)),
        )
        return True

    def upsert_env_bearer(
        self, secret: str, *, name: str = _GROKBOT, can_auth_start: bool = True
    ) -> str:
        if not secret:
            raise ValueError("empty bearer")
        existing = self._fetchone("SELECT id FROM tenant WHERE name = ?", (name,))
        digest = sha256_secret(secret)
        prefix = secret[:12]
        if existing:
            self._exec(
                """
                UPDATE tenant SET token_hash = ?, display_prefix = ?,
                    can_auth_start = ?, revoked_at = NULL
                WHERE id = ?
                """,
                (digest, prefix, int(can_auth_start), existing["id"]),
            )
            return existing["id"]
        tid = new_id("tnt")
        self._exec(
            """
            INSERT INTO tenant (id, name, token_hash, display_prefix, can_auth_start, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tid, name, digest, prefix, int(can_auth_start), _now()),
        )
        return tid

    def grant(self, tenant_id: str, account: str) -> None:
        email = account.strip().lower()
        if "@" not in email:
            raise ValueError(f"Not an email address: {account!r}")
        self._exec(
            """
            INSERT OR IGNORE INTO account_grant (tenant_id, account, granted_at)
            VALUES (?, ?, ?)
            """,
            (tenant_id, email, _now()),
        )

    def revoke_grant(self, tenant_id: str, account: str) -> None:
        self._exec(
            "DELETE FROM account_grant WHERE tenant_id = ? AND account = ?",
            (tenant_id, account.strip().lower()),
        )

    def grant_all(self, tenant_id: str, accounts: list[str]) -> None:
        for account in accounts:
            self.grant(tenant_id, account)

    def tenant_by_name(self, name: str) -> Tenant | None:
        row = self._fetchone(
            "SELECT * FROM tenant WHERE name = ? AND revoked_at IS NULL", (name,)
        )
        return self._tenant_from_row(row) if row else None

    def resolve_bearer(self, secret: str) -> Tenant | None:
        if not secret:
            return None
        row = self._fetchone(
            "SELECT * FROM tenant WHERE token_hash = ? AND revoked_at IS NULL",
            (sha256_secret(secret),),
        )
        if not row:
            return None
        self._exec(
            "UPDATE tenant SET last_used_at = ? WHERE id = ?",
            (_now(), row["id"]),
        )
        return self._tenant_from_row(row)

    def _tenant_from_row(self, row: sqlite3.Row) -> Tenant:
        grants = self._fetchall(
            "SELECT account FROM account_grant WHERE tenant_id = ?", (row["id"],)
        )
        return Tenant(
            id=row["id"],
            name=row["name"],
            can_auth_start=bool(row["can_auth_start"]),
            grants=frozenset(r["account"] for r in grants),
        )

    def list_tenants(self) -> list[dict]:
        rows = self._fetchall(
            "SELECT * FROM tenant WHERE revoked_at IS NULL ORDER BY created_at"
        )
        out = []
        for row in rows:
            tenant = self._tenant_from_row(row)
            out.append(
                {
                    "id": tenant.id,
                    "name": tenant.name,
                    "displayPrefix": row["display_prefix"],
                    "canAuthStart": tenant.can_auth_start,
                    "grants": sorted(tenant.grants),
                    "createdAt": row["created_at"],
                    "lastUsedAt": row["last_used_at"],
                }
            )
        return out

    def create_tenant(self, name: str, *, can_auth_start: bool = False) -> tuple[str, str]:
        name = name.strip().lower()
        if not name or not name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Tenant name must be letters, digits, hyphen, underscore.")
        if self._fetchone("SELECT 1 FROM tenant WHERE name = ? AND revoked_at IS NULL", (name,)):
            raise ValueError(f"Tenant {name!r} already exists.")
        secret = new_api_secret()
        tid = new_id("tnt")
        self._exec(
            """
            INSERT INTO tenant (id, name, token_hash, display_prefix, can_auth_start, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (tid, name, sha256_secret(secret), secret[:12], int(can_auth_start), _now()),
        )
        return tid, secret

    def revoke_tenant(self, tenant_id: str) -> None:
        self._exec(
            "UPDATE tenant SET revoked_at = ? WHERE id = ?",
            (_now(), tenant_id),
        )

    def set_can_auth_start(self, tenant_id: str, value: bool) -> None:
        self._exec(
            "UPDATE tenant SET can_auth_start = ? WHERE id = ?",
            (int(value), tenant_id),
        )

    def rotate_secret(self, tenant_id: str) -> str:
        secret = new_api_secret()
        self._exec(
            "UPDATE tenant SET token_hash = ?, display_prefix = ? WHERE id = ?",
            (sha256_secret(secret), secret[:12], tenant_id),
        )
        return secret

    def put_challenge(self, challenge: str, payload: dict) -> None:
        self._gc_challenges()
        self._exec(
            "INSERT OR REPLACE INTO webauthn_challenge (challenge, payload, expires_at) VALUES (?, ?, ?)",
            (challenge, json.dumps(payload), _iso(datetime.now(timezone.utc) + _CHALLENGE_TTL)),
        )

    def pop_challenge(self, challenge: str) -> dict | None:
        self._gc_challenges()
        row = self._fetchone(
            "SELECT payload, expires_at FROM webauthn_challenge WHERE challenge = ?",
            (challenge,),
        )
        if not row or row["expires_at"] < _now():
            return None
        self._exec("DELETE FROM webauthn_challenge WHERE challenge = ?", (challenge,))
        return json.loads(row["payload"])

    def _gc_challenges(self) -> None:
        self._exec(
            "DELETE FROM webauthn_challenge WHERE expires_at < ?",
            (_now(),),
        )

    def add_passkey(
        self,
        *,
        user_id: str,
        credential_id: bytes,
        public_key: bytes,
        sign_count: int,
        name: str,
    ) -> str:
        pid = new_id("pky")
        self._exec(
            """
            INSERT INTO passkey_credential
                (id, user_id, credential_id, public_key, sign_count, name, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (pid, user_id, credential_id, public_key, sign_count, name, _now()),
        )
        return pid

    def passkey_by_credential_id(self, credential_id: bytes) -> sqlite3.Row | None:
        return self._fetchone(
            "SELECT * FROM passkey_credential WHERE credential_id = ?",
            (credential_id,),
        )

    def update_passkey_count(self, passkey_id: str, sign_count: int) -> None:
        self._exec(
            "UPDATE passkey_credential SET sign_count = ?, last_used_at = ? WHERE id = ?",
            (sign_count, _now(), passkey_id),
        )

    def create_session(self, user_id: str, purpose: str = "full") -> str:
        secret = secrets.token_urlsafe(32)
        sid = new_id("ses")
        self._exec(
            """
            INSERT INTO session (id, user_id, token_hash, purpose, expires_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (sid, user_id, sha256_secret(secret), purpose, _iso(datetime.now(timezone.utc) + _SESSION_TTL)),
        )
        return secret

    def resolve_session(self, secret: str) -> AdminSession | None:
        if not secret:
            return None
        row = self._fetchone(
            "SELECT * FROM session WHERE token_hash = ?",
            (sha256_secret(secret),),
        )
        if not row or row["expires_at"] < _now():
            return None
        return AdminSession(id=row["id"], user_id=row["user_id"], purpose=row["purpose"])

    def audit(
        self,
        *,
        tenant_name: str,
        tool: str,
        account: str = "",
        from_identity: str = "",
        target_id: str = "",
    ) -> None:
        self._exec(
            """
            INSERT INTO audit_event (id, at, tenant_name, tool, account, from_identity, target_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (new_id("aud"), _now(), tenant_name, tool, account, from_identity, target_id),
        )

    def list_audit(self, limit: int = 100) -> list[dict]:
        rows = self._fetchall(
            """
            SELECT at, tenant_name, tool, account, from_identity, target_id
            FROM audit_event ORDER BY at DESC LIMIT ?
            """,
            (limit,),
        )
        return [dict(r) for r in rows]

"""Named tenants, grants, and the env-token grokbot seed."""

from __future__ import annotations

from pigeon_mcp.oauth_constants import STATUS_ACTIVE
from pigeon_mcp.tenant_store import sha256_secret
from pigeon_mcp.tenants import current_tenant, gate_http, get_store, set_current_tenant
from pigeon_mcp.token_store import AccountToken, TokenStore


def test_env_bearer_seeds_grokbot_and_grants_disk_accounts(tmp_path):
    tokens = tmp_path / "tokens"
    store = TokenStore(tokens)
    store.save(
        AccountToken(email="mail@example.com", refresh_token="rt", status=STATUS_ACTIVE)
    )
    from pigeon_mcp.config import settings

    settings.tokens_dir = tokens  # autouse already set; keep aligned
    db = get_store()
    tenant = db.resolve_bearer("test-token")
    assert tenant is not None
    assert tenant.name == "grokbot"
    assert tenant.can_auth_start
    assert tenant.allows("mail@example.com")


def test_harness_tenant_cannot_see_ungranted_account():
    db = get_store()
    _tid, secret = db.create_tenant("cursor", can_auth_start=False)
    tenant = db.resolve_bearer(secret)
    assert tenant is not None
    set_current_tenant(tenant)
    try:
        gate_http("accounts_auth_start")
        raise AssertionError("expected auth_start deny")
    except ValueError as exc:
        assert "cannot connect mailboxes" in str(exc)
    try:
        gate_http("send", account="mail@example.com")
        raise AssertionError("expected grant deny")
    except ValueError as exc:
        assert "not granted" in str(exc)
    db.grant(tenant.id, "mail@example.com")
    tenant = db.resolve_bearer(secret)
    set_current_tenant(tenant)
    gate_http("send", account="mail@example.com", from_identity="cursor@example.com")
    rows = db.list_audit()
    assert rows[0]["tenant_name"] == "cursor"
    assert rows[0]["tool"] == "send"
    assert rows[0]["from_identity"] == "cursor@example.com"
    set_current_tenant(None)


def test_stdio_has_no_tenant_gate():
    set_current_tenant(None)
    assert current_tenant() is None
    gate_http("send", account="anyone@example.com")


def test_revoked_tenant_bearer_fails():
    db = get_store()
    tid, secret = db.create_tenant("codex")
    assert db.resolve_bearer(secret) is not None
    db.revoke_tenant(tid)
    assert db.resolve_bearer(secret) is None


def test_token_hash_is_not_the_secret():
    db = get_store()
    _tid, secret = db.create_tenant("claude")
    row = db._fetchone("SELECT token_hash FROM tenant WHERE name = ?", ("claude",))
    assert row["token_hash"] == sha256_secret(secret)
    assert secret.encode() not in row["token_hash"]

"""Settings / dotenv loading — env-only deploys must not crash on import."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import SettingsConfigDict

from pigeon_mcp import config
from pigeon_mcp.config import Settings, _dotenv_files


def test_dotenv_files_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "_KEYS_FILE", tmp_path / "missing.keys")
    assert _dotenv_files() is None


def test_dotenv_files_only_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("PIGEON_MCP_ENVIRONMENT=test\n")
    monkeypatch.setattr(config, "_ENV_FILE", env)
    monkeypatch.setattr(config, "_KEYS_FILE", tmp_path / "missing.keys")
    assert _dotenv_files() == (env,)


def test_settings_env_only_no_dotenv(monkeypatch):
    """systemd/Docker pass Environment= only — env_file=None must boot."""
    monkeypatch.setenv("PIGEON_MCP_HTTP_PORT", "9999")

    class EnvOnly(Settings):
        model_config = SettingsConfigDict(
            env_prefix="PIGEON_MCP_",
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

    s = EnvOnly()
    assert s.http_port == 9999


def test_path_fields_expand_tilde(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PIGEON_MCP_TOKENS_DIR", "~/.config/pigeon-mcp/tokens")
    monkeypatch.setenv("PIGEON_MCP_OUTBOX_ROOT", "~/Outbox")

    class EnvOnly(Settings):
        model_config = SettingsConfigDict(
            env_prefix="PIGEON_MCP_",
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

    s = EnvOnly()
    assert s.tokens_dir.is_absolute()
    assert "~" not in str(s.tokens_dir)
    assert s.tokens_dir == home / ".config" / "pigeon-mcp" / "tokens"
    assert s.outbox_root == home / "Outbox"


def test_http_transport_security_allows_public_host():
    from pigeon_mcp.config import http_transport_security

    cfg = Settings(
        http_host="127.0.0.1",
        http_port=8879,
        oauth_public_redirect_uri="https://pigeon.example.com/oauth/callback",
    )
    ts = http_transport_security(cfg)
    assert ts is not None
    assert "pigeon.example.com" in ts.allowed_hosts
    assert "https://pigeon.example.com" in ts.allowed_origins


def test_http_transport_security_none_for_local_only():
    from pigeon_mcp.config import http_transport_security

    cfg = Settings(
        http_host="127.0.0.1",
        http_port=8879,
        http_public_url="",
        oauth_public_redirect_uri="",
    )
    assert http_transport_security(cfg) is None

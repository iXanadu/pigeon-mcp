"""Settings / dotenv loading — env-only deploys must not crash on import."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import SettingsConfigDict

from gmail_mcp import config
from gmail_mcp.config import Settings, _dotenv_files


def test_dotenv_files_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_ENV_FILE", tmp_path / "missing.env")
    monkeypatch.setattr(config, "_KEYS_FILE", tmp_path / "missing.keys")
    assert _dotenv_files() is None


def test_dotenv_files_only_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("GMAIL_MCP_ENVIRONMENT=test\n")
    monkeypatch.setattr(config, "_ENV_FILE", env)
    monkeypatch.setattr(config, "_KEYS_FILE", tmp_path / "missing.keys")
    assert _dotenv_files() == (env,)


def test_settings_env_only_no_dotenv(monkeypatch):
    """systemd/Docker pass Environment= only — env_file=None must boot."""
    monkeypatch.setenv("GMAIL_MCP_HTTP_PORT", "9999")

    class EnvOnly(Settings):
        model_config = SettingsConfigDict(
            env_prefix="GMAIL_MCP_",
            env_file=None,
            env_file_encoding="utf-8",
            extra="ignore",
        )

    s = EnvOnly()
    assert s.http_port == 9999

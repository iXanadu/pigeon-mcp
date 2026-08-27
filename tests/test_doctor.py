"""Doctor checks config without touching Gmail."""

from unittest.mock import patch

from gmail_mcp import doctor
from gmail_mcp.config import settings as cfg


def test_doctor_warns_without_oauth(tmp_path, capsys):
    with patch.object(cfg, "outbox_root", tmp_path / "Outbox"), patch.object(
        cfg, "tokens_dir", tmp_path / "tokens"
    ), patch.object(cfg, "google_client_id", ""), patch.object(
        cfg, "google_client_secret", ""
    ), patch.object(cfg, "http_bearer_token", ""):
        rc = doctor.run()
    out = capsys.readouterr().out
    assert rc == 0
    assert "OAuth client credentials not set" in out


def test_doctor_passes_with_outbox_and_tokens(tmp_path, capsys):
    outbox = tmp_path / "Outbox"
    tokens = tmp_path / "tokens"
    outbox.mkdir()
    tokens.mkdir()
    with patch.object(cfg, "outbox_root", outbox), patch.object(
        cfg, "tokens_dir", tokens
    ), patch.object(cfg, "google_client_id", "id"), patch.object(
        cfg, "google_client_secret", "secret"
    ), patch.object(cfg, "http_bearer_token", "tok"):
        rc = doctor.run()
    out = capsys.readouterr().out
    assert rc == 0
    assert "Outbox root exists" in out
    assert "Google OAuth client credentials loaded" in out

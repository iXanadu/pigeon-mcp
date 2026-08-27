"""Doctor checks config without touching Gmail."""

import os
from pathlib import Path
from unittest.mock import patch

from pigeon_mcp import doctor
from pigeon_mcp.config import settings as cfg


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
    assert "Outbox root ready" in out
    assert "Google OAuth client credentials loaded" in out


def test_ensure_data_dirs_recreates_tmp_tree(tmp_path, monkeypatch):
    """Self-heal: missing /tmp-style roots are created 0700 including parent."""
    import shutil
    import stat

    from pigeon_mcp.config import ensure_data_dirs, settings

    real = Path("/tmp") / f"pigeon-test-{os.getpid()}"
    try:
        monkeypatch.setattr(settings, "outbox_root", real / "Outbox")
        monkeypatch.setattr(settings, "download_root", real / "Inbox")
        monkeypatch.setattr(settings, "tokens_dir", tmp_path / "tokens")
        ensure_data_dirs()
        assert (real / "Outbox").is_dir()
        assert (real / "Inbox").is_dir()
        assert stat.S_IMODE((real / "Outbox").stat().st_mode) == 0o700
        assert stat.S_IMODE(real.stat().st_mode) == 0o700
    finally:
        shutil.rmtree(real, ignore_errors=True)


def test_ensure_data_dirs_repairs_preexisting_755(monkeypatch):
    """chmod runs even when mkdir is a no-op — repairs README mkdir -p at 755."""
    import shutil
    import stat

    from pigeon_mcp.config import ensure_data_dirs, settings

    real = Path("/tmp") / f"pigeon-test755-{os.getpid()}"
    try:
        real.mkdir(mode=0o755)
        (real / "Outbox").mkdir(mode=0o755)
        (real / "Inbox").mkdir(mode=0o755)
        monkeypatch.setattr(settings, "outbox_root", real / "Outbox")
        monkeypatch.setattr(settings, "download_root", real / "Inbox")
        monkeypatch.setattr(settings, "tokens_dir", Path("/tmp") / f"pigeon-tok-{os.getpid()}")
        ensure_data_dirs()
        assert stat.S_IMODE((real / "Outbox").stat().st_mode) == 0o700
        assert stat.S_IMODE(real.stat().st_mode) == 0o700
        ensure_data_dirs()
        assert stat.S_IMODE((real / "Outbox").stat().st_mode) == 0o700
    finally:
        shutil.rmtree(real, ignore_errors=True)
        shutil.rmtree(Path("/tmp") / f"pigeon-tok-{os.getpid()}", ignore_errors=True)

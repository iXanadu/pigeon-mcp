"""24-hour file sweep over outbox + download roots (privacy policy promise)."""

from __future__ import annotations

import os
import time

import pytest

from pigeon_mcp.attachments import sweep_old_files
from pigeon_mcp.config import settings
from pigeon_mcp.http_server import sweep_file_roots

DAY = 24 * 3600


def _age(path, seconds):
    t = time.time() - seconds
    os.utime(path, (t, t), follow_symlinks=False)


def test_sweep_removes_old_keeps_fresh_and_prunes_empty_dirs(tmp_path):
    root = tmp_path / "Inbox"
    old = root / "tnt_a" / "old.pdf"
    fresh = root / "tnt_b" / "fresh.pdf"
    old.parent.mkdir(parents=True)
    fresh.parent.mkdir(parents=True)
    old.write_bytes(b"x")
    fresh.write_bytes(b"y")
    _age(old, DAY + 60)
    assert sweep_old_files(root, DAY) == 1
    assert not old.exists()
    assert not old.parent.exists()
    assert fresh.exists()
    assert root.is_dir()


def test_sweep_unlinks_symlink_not_its_target(tmp_path):
    root = tmp_path / "Inbox"
    root.mkdir()
    outside = tmp_path / "keep.txt"
    outside.write_bytes(b"keep")
    link = root / "link.txt"
    link.symlink_to(outside)
    _age(link, DAY + 60)
    _age(outside, DAY + 60)
    sweep_old_files(root, DAY)
    assert not link.is_symlink()
    assert outside.read_bytes() == b"keep"


def test_sweep_does_not_descend_symlinked_dir(tmp_path):
    root = tmp_path / "Inbox"
    root.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    victim = elsewhere / "victim.txt"
    victim.write_bytes(b"v")
    _age(victim, DAY + 60)
    (root / "dirlink").symlink_to(elsewhere, target_is_directory=True)
    sweep_old_files(root, DAY)
    assert victim.exists()


def test_sweep_refuses_root_containing_tokens(tmp_path):
    tokens = tmp_path / "state" / "tokens"
    tokens.mkdir(parents=True)
    with pytest.raises(ValueError, match="refusing to sweep"):
        sweep_old_files(tmp_path / "state", DAY, protect=(tokens,))
    with pytest.raises(ValueError, match="refusing to sweep"):
        sweep_old_files(tokens, DAY, protect=(tokens,))


def test_sweep_missing_root_is_noop(tmp_path):
    assert sweep_old_files(tmp_path / "nope", DAY) == 0


def test_server_sweep_covers_outbox_and_download(tmp_path, monkeypatch):
    outbox = tmp_path / "Outbox"
    inbox = tmp_path / "Inbox"
    outbox.mkdir()
    inbox.mkdir()
    monkeypatch.setattr(settings, "outbox_root", outbox)
    monkeypatch.setattr(settings, "download_root", inbox)
    for f in (outbox / "staged.png", inbox / "pulled.pdf"):
        f.write_bytes(b"z")
        _age(f, DAY + 60)
    assert sweep_file_roots() == 2


def test_server_sweep_off_when_ttl_zero(tmp_path, monkeypatch):
    inbox = tmp_path / "Inbox"
    inbox.mkdir()
    monkeypatch.setattr(settings, "download_root", inbox)
    monkeypatch.setattr(settings, "file_ttl_hours", 0)
    f = inbox / "pulled.pdf"
    f.write_bytes(b"z")
    _age(f, DAY * 30)
    assert sweep_file_roots() == 0
    assert f.exists()

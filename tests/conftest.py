import os
import sys

# Test THIS tree, not whichever tree the shared venv's editable install points at.
_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for _m in [m for m in list(sys.modules) if m == "gmail_mcp" or m.startswith("gmail_mcp.")]:
    del sys.modules[_m]

import pytest

import gmail_mcp.config as config_mod


@pytest.fixture(autouse=True)
def _isolate_settings(monkeypatch, tmp_path):
    """Pin settings to deterministic values for every test."""
    monkeypatch.setattr(config_mod.settings, "environment", "test")
    monkeypatch.setattr(config_mod.settings, "log_level", "info")
    monkeypatch.setattr(config_mod.settings, "http_host", "127.0.0.1")
    monkeypatch.setattr(config_mod.settings, "http_port", 8879)
    monkeypatch.setattr(config_mod.settings, "http_bearer_token", "test-token")
    monkeypatch.setattr(config_mod.settings, "outbox_root", tmp_path / "Outbox")
    monkeypatch.setattr(config_mod.settings, "tokens_dir", tmp_path / "tokens")
    monkeypatch.setattr(config_mod.settings, "google_client_id", "")
    monkeypatch.setattr(config_mod.settings, "google_client_secret", "")

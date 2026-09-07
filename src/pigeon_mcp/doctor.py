"""pigeon-mcp doctor — config sanity check before wiring Gmail OAuth."""

from __future__ import annotations

import sys

from pigeon_mcp.config import admin_db_path, ensure_data_dirs, settings
from pigeon_mcp.tenants import get_store

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def _line(level: str, msg: str, fix: str = "") -> tuple[str, str, str]:
    return level, msg, fix


def run() -> int:
    results: list[tuple[str, str, str]] = []

    results.append(_line(PASS, f"Package import ok; environment={settings.environment}."))

    ensure_data_dirs()

    outbox = settings.outbox_root.expanduser()
    results.append(_line(PASS, f"Outbox root ready: {outbox}."))

    download = settings.download_root.expanduser()
    results.append(_line(PASS, f"Download root ready: {download}."))

    tokens = settings.tokens_dir.expanduser()
    results.append(_line(PASS, f"Tokens dir ready: {tokens}."))

    if settings.google_client_id and settings.google_client_secret:
        results.append(_line(PASS, "Google OAuth client credentials loaded."))
    else:
        results.append(
            _line(
                WARN,
                "Google OAuth client credentials not set.",
                "Add PIGEON_MCP_GOOGLE_CLIENT_ID and PIGEON_MCP_GOOGLE_CLIENT_SECRET to .keys.",
            )
        )

    if settings.http_bearer_token:
        results.append(_line(PASS, "HTTP bearer token configured (seeded as tenant grokbot)."))
    else:
        results.append(
            _line(
                WARN,
                "HTTP bearer token not set.",
                "Add PIGEON_MCP_HTTP_BEARER_TOKEN to .keys for GrokBot / gateway transport.",
            )
        )

    db = admin_db_path()
    store = get_store()
    results.append(_line(PASS, f"Admin SQLite ready: {db}."))
    if store.has_passkey():
        results.append(_line(PASS, f"Owner passkey registered ({store.passkey_count()})."))
    else:
        results.append(
            _line(
                WARN,
                "No owner passkey yet.",
                "Run pigeon-admin bootstrap and open the URL to register a passkey.",
            )
        )

    worst = PASS
    for level, msg, fix in results:
        print(f"[{level}] {msg}")
        if fix:
            print(f"       fix: {fix}")
        if level == FAIL or (level == WARN and worst == PASS):
            worst = level

    if worst == FAIL:
        return 1
    return 0


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()

"""gmail-mcp doctor — config sanity check before wiring Gmail OAuth."""

from __future__ import annotations

import sys

from gmail_mcp.config import ensure_data_dirs, settings

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
                "Add GMAIL_MCP_GOOGLE_CLIENT_ID and GMAIL_MCP_GOOGLE_CLIENT_SECRET to .keys.",
            )
        )

    if settings.http_bearer_token:
        results.append(_line(PASS, "HTTP bearer token configured."))
    else:
        results.append(
            _line(
                WARN,
                "HTTP bearer token not set.",
                "Add GMAIL_MCP_HTTP_BEARER_TOKEN to .keys for gateway/Hand transport.",
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

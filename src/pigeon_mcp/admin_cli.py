"""Owner bootstrap — print a one-time passkey setup URL."""

from __future__ import annotations

import argparse
import sys

from pigeon_mcp.config import admin_db_path, ensure_data_dirs, http_public_base_url
from pigeon_mcp.tenants import get_store


def bootstrap() -> int:
    ensure_data_dirs()
    store = get_store()
    if store.has_passkey():
        print(
            f"Owner passkey already registered. Admin is {http_public_base_url()}/~/",
            file=sys.stderr,
        )
        print(f"SQLite: {admin_db_path()}", file=sys.stderr)
        return 0
    token = store.create_setup_token()
    url = f"{http_public_base_url()}/~/setup?t={token}"
    print("Open this URL on the owner's computer and register a passkey.")
    print("It expires in 30 minutes. It will not be shown again.")
    print(url)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="pigeon-admin")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bootstrap", help="Print a one-time owner passkey setup URL")
    args = parser.parse_args()
    if args.cmd == "bootstrap":
        sys.exit(bootstrap())
    parser.error("unknown command")


if __name__ == "__main__":
    main()

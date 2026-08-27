"""Gmail MCP stdio entrypoint — all tools including accounts_add/remove."""

import asyncio

from gmail_mcp.app import build_mcp
from gmail_mcp.config import ensure_data_dirs


async def _amain() -> None:
    ensure_data_dirs()
    mcp = build_mcp(http=False)
    await mcp.run_stdio_async()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()

"""Gmail MCP Streamable HTTP entrypoint — bearer auth, Hand tool allow-list."""

import asyncio

from gmail_mcp.app import build_mcp
from gmail_mcp.config import ensure_data_dirs, settings


async def _amain() -> None:
    ensure_data_dirs()
    mcp = build_mcp(http=True)
    await mcp.run_streamable_http_async(
        host=settings.http_host,
        port=settings.http_port,
        streamable_http_path="/mcp",
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()

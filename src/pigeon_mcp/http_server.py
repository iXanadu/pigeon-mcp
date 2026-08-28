"""Gmail MCP Streamable HTTP entrypoint — bearer auth, Hand tool allow-list."""

import asyncio

from pigeon_mcp.app import build_mcp
from pigeon_mcp.config import ensure_data_dirs, http_transport_security, settings


async def _amain() -> None:
    ensure_data_dirs()
    mcp = build_mcp(http=True)
    await mcp.run_streamable_http_async(
        host=settings.http_host,
        port=settings.http_port,
        streamable_http_path="/mcp",
        transport_security=http_transport_security(),
    )


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()

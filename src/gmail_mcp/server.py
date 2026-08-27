"""Gmail MCP server — stdio for local harnesses; HTTP transport added separately."""

import asyncio
import json

from mcp.server.mcpserver import MCPServer

from gmail_mcp import accounts as accounts_mod
from gmail_mcp.config import settings

VERSION = "0.1.0"

mcp = MCPServer("gmail-mcp", version=VERSION)


@mcp.tool()
async def gmail_status() -> str:
    """Report server version and configuration (no Gmail API calls)."""
    accts = await accounts_mod.accounts_list()
    return (
        f"gmail-mcp {VERSION}\n"
        f"environment: {settings.environment}\n"
        f"outbox_root: {settings.outbox_root}\n"
        f"http: {settings.http_host}:{settings.http_port}\n"
        f"accounts: {len(accts)} connected"
    )


@mcp.tool()
async def accounts_list() -> str:
    """List connected Gmail addresses and whether each refresh token still works."""
    rows = await accounts_mod.accounts_list()
    return json.dumps(rows, indent=2)


@mcp.tool()
async def accounts_add() -> str:
    """Start Google OAuth to connect a Gmail account. Returns a browser URL."""
    result = await accounts_mod.accounts_add()
    return json.dumps(result, indent=2)


@mcp.tool()
async def accounts_remove(account: str) -> str:
    """Remove a connected Gmail account and revoke its token at Google."""
    result = await accounts_mod.accounts_remove(account)
    return json.dumps(result, indent=2)


async def _amain() -> None:
    await mcp.run_stdio_async()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()

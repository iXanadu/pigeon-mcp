"""Smoke tests for the scaffolded MCP server."""

from gmail_mcp.server import VERSION, gmail_status


async def test_version():
    assert VERSION == "0.1.0"


async def test_gmail_status():
    result = await gmail_status()
    assert "gmail-mcp" in result
    assert "accounts:" in result

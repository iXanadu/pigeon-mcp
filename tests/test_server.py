"""Smoke tests for the scaffolded MCP server."""

from pigeon_mcp.app import HTTP_TOOL_NAMES, VERSION, build_mcp


async def test_version():
    assert VERSION == "0.1.0"


async def test_gmail_status():
    mcp = build_mcp(http=False)
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    assert "gmail_status" in tools
    result = await tools["gmail_status"].fn()
    assert "pigeon-mcp" in result
    assert "accounts:" in result


async def test_http_tool_allow_list():
    http = build_mcp(http=True)
    stdio = build_mcp(http=False)
    http_names = {t.name for t in http._tool_manager.list_tools()}
    stdio_names = {t.name for t in stdio._tool_manager.list_tools()}
    assert http_names == HTTP_TOOL_NAMES
    assert stdio_names - http_names == {"accounts_add", "accounts_remove"}

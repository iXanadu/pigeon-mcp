"""Temporary localhost server to capture Google OAuth redirect."""

from __future__ import annotations

import asyncio
from urllib.parse import parse_qs, urlparse

from gmail_mcp.google_oauth import verify_state

_HOST = "127.0.0.1"


async def run_callback_server(expected_state: str, redirect_uri: str) -> str | None:
    """Listen once for OAuth callback. Returns authorization code or None on timeout."""
    parsed = urlparse(redirect_uri)
    port = parsed.port or 8767
    path = parsed.path or "/oauth/callback"
    result: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            request_line = (await reader.readline()).decode("utf-8", errors="replace").strip()
            if not request_line.startswith("GET "):
                writer.close()
                return
            req_target = request_line.split(" ", 2)[1]
            parsed_req = urlparse(req_target)
            if parsed_req.path != path:
                writer.close()
                return
            params = parse_qs(parsed_req.query)
            code = (params.get("code") or [None])[0]
            state = (params.get("state") or [None])[0]
            body = b"OAuth complete. You can close this tab."
            if code and state and state == expected_state and verify_state(state):
                if not result.done():
                    result.set_result(code)
            else:
                body = b"OAuth failed or state mismatch."
            response = (
                b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: "
                + str(len(body)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            writer.write(response)
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    server = await asyncio.start_server(handle, _HOST, port)
    try:
        return await asyncio.wait_for(result, timeout=300.0)
    except asyncio.TimeoutError:
        return None
    finally:
        server.close()
        await server.wait_closed()

"""MCPServer factory — stdio (all tools) vs HTTP (Hand allow-list)."""

from __future__ import annotations

import base64
import json
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, RedirectResponse, Response

from gmail_mcp import accounts as accounts_mod
from gmail_mcp import inbox as inbox_mod
from gmail_mcp import mail as mail_mod
from gmail_mcp.bearer_auth import StaticBearerVerifier
from gmail_mcp.config import http_public_base_url, settings

VERSION = "0.1.0"

# One-time auth codes for Hand's authorization_code bootstrap (static bearer AS).
_AUTH_CODES: dict[str, dict[str, float | str]] = {}
_AUTH_CODE_TTL_SEC = 300.0

# Hand / gateway may call these over HTTP.
HTTP_TOOL_NAMES = frozenset(
    {
        "gmail_status",
        "accounts_list",
        "accounts_auth_start",
        "search",
        "get_thread",
        "get_message",
        "get_attachment",
        "labels_list",
        "labels_create",
        "label",
        "unlabel",
        "archive",
        "trash",
        "untrash",
        "draft_create",
        "draft_send",
        "send",
        "reply",
        "forward",
    }
)

# Local browser loopback consent + remove stay on stdio.
STDIO_ONLY_TOOL_NAMES = frozenset({"accounts_add", "accounts_remove"})


def _parse_attachments(attachments_json: str) -> list[dict]:
    if not attachments_json or attachments_json.strip() in ("", "[]"):
        return []
    data = json.loads(attachments_json)
    if not isinstance(data, list):
        raise ValueError("attachments_json must be a JSON array")
    return data


def build_mcp(*, http: bool = False) -> MCPServer:
    if http:
        if not settings.http_bearer_token:
            raise RuntimeError("GMAIL_MCP_HTTP_BEARER_TOKEN is required for HTTP transport")
        public_base = http_public_base_url()
        resource_url = AnyHttpUrl(f"{public_base.rstrip('/')}/mcp")
        auth = AuthSettings(
            issuer_url=public_base,
            resource_server_url=resource_url,
        )
        mcp = MCPServer(
            "gmail-mcp",
            version=VERSION,
            auth=auth,
            token_verifier=StaticBearerVerifier(settings.http_bearer_token),
        )
    else:
        mcp = MCPServer("gmail-mcp", version=VERSION)

    if http:

        def _gc_auth_codes() -> None:
            cutoff = time.time() - _AUTH_CODE_TTL_SEC
            stale = [k for k, v in _AUTH_CODES.items() if float(v["created"]) < cutoff]
            for k in stale:
                _AUTH_CODES.pop(k, None)

        def _client_secret_from_request(request: Request, form: dict) -> str | None:
            secret = form.get("client_secret")
            if secret:
                return str(secret)
            auth = request.headers.get("authorization", "")
            if auth.lower().startswith("basic "):
                try:
                    decoded = base64.b64decode(auth.split(" ", 1)[1]).decode()
                    return decoded.split(":", 1)[1] if ":" in decoded else decoded
                except Exception:
                    return None
            return None

        def _issue_bearer() -> JSONResponse:
            return JSONResponse(
                {
                    "access_token": settings.http_bearer_token,
                    "token_type": "Bearer",
                    "expires_in": 86400,
                }
            )

        @mcp.custom_route("/.well-known/oauth-authorization-server", methods=["GET"])
        async def mcp_oauth_metadata(_request: Request) -> Response:
            """AS metadata for Hand connector bootstrap (static bearer behind auth code)."""
            return JSONResponse(
                {
                    "issuer": public_base,
                    "authorization_endpoint": f"{public_base}/authorize",
                    "token_endpoint": f"{public_base}/token",
                    "registration_endpoint": f"{public_base}/register",
                    "response_types_supported": ["code"],
                    "grant_types_supported": ["authorization_code", "client_credentials"],
                    "code_challenge_methods_supported": ["S256", "plain"],
                    "token_endpoint_auth_methods_supported": [
                        "client_secret_post",
                        "client_secret_basic",
                        "none",
                    ],
                }
            )

        @mcp.custom_route("/register", methods=["POST"])
        async def mcp_oauth_register(request: Request) -> Response:
            """Dynamic client registration — returns a client that can redeem the static bearer."""
            try:
                body = await request.json()
            except Exception:
                body = {}
            redirect_uris = body.get("redirect_uris") or []
            return JSONResponse(
                {
                    "client_id": "gmail-mcp-hand",
                    "client_secret": settings.http_bearer_token,
                    "redirect_uris": redirect_uris,
                    "grant_types": ["authorization_code", "client_credentials"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "client_secret_post",
                },
                status_code=201,
            )

        @mcp.custom_route("/authorize", methods=["GET"])
        async def mcp_oauth_authorize(request: Request) -> Response:
            """No login UI — immediately issue a one-time code and redirect back to Hand."""
            if request.query_params.get("response_type", "code") != "code":
                return PlainTextResponse("unsupported_response_type", status_code=400)
            redirect_uri = request.query_params.get("redirect_uri")
            if not redirect_uri:
                return PlainTextResponse("missing redirect_uri", status_code=400)
            state = request.query_params.get("state", "")
            _gc_auth_codes()
            code = secrets.token_urlsafe(24)
            _AUTH_CODES[code] = {
                "created": time.time(),
                "redirect_uri": redirect_uri,
            }
            parts = urlsplit(redirect_uri)
            q = dict(parse_qsl(parts.query, keep_blank_values=True))
            q["code"] = code
            if state:
                q["state"] = state
            target = urlunsplit(
                (parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment)
            )
            return RedirectResponse(target, status_code=302)

        @mcp.custom_route("/token", methods=["POST"])
        async def mcp_oauth_token(request: Request) -> Response:
            """Issue configured bearer for authorization_code or client_credentials."""
            form = dict(await request.form())
            grant = form.get("grant_type")
            if grant == "client_credentials":
                secret = _client_secret_from_request(request, form)
                if secret != settings.http_bearer_token:
                    return JSONResponse({"error": "invalid_client"}, status_code=401)
                return _issue_bearer()
            if grant == "authorization_code":
                code = str(form.get("code") or "")
                redirect_uri = str(form.get("redirect_uri") or "")
                _gc_auth_codes()
                pending = _AUTH_CODES.pop(code, None)
                if not pending:
                    return JSONResponse({"error": "invalid_grant"}, status_code=400)
                if redirect_uri and redirect_uri != pending["redirect_uri"]:
                    return JSONResponse({"error": "invalid_grant"}, status_code=400)
                return _issue_bearer()
            return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)

        @mcp.custom_route("/oauth/callback", methods=["GET"])
        async def oauth_callback(request: Request) -> Response:
            """Public Google redirect — protected by one-time state + PKCE, not bearer."""
            code = request.query_params.get("code")
            state = request.query_params.get("state")
            err = request.query_params.get("error")
            if err:
                return PlainTextResponse(f"OAuth error: {err}", status_code=400)
            if not code or not state:
                return PlainTextResponse("Missing code or state", status_code=400)
            try:
                result = await accounts_mod.accounts_add_complete(code, state)
            except ValueError as exc:
                return PlainTextResponse(str(exc), status_code=400)
            except Exception as exc:
                return PlainTextResponse(f"OAuth failed: {exc}", status_code=500)
            return PlainTextResponse(
                f"Gmail connected: {result['account']}. You can close this tab.",
                status_code=200,
            )

    @mcp.tool()
    async def gmail_status() -> str:
        """Report server version and configuration (no Gmail API calls)."""
        accts = await accounts_mod.accounts_list()
        return (
            f"gmail-mcp {VERSION}\n"
            f"environment: {settings.environment}\n"
            f"outbox_root: {settings.outbox_root}\n"
            f"download_root: {settings.download_root}\n"
            f"http: {settings.http_host}:{settings.http_port}\n"
            f"accounts: {len(accts)} connected"
        )

    @mcp.tool()
    async def accounts_list() -> str:
        """List connected Gmail addresses and whether each refresh token still works."""
        rows = await accounts_mod.accounts_list()
        return json.dumps(rows, indent=2)

    @mcp.tool()
    async def accounts_auth_start() -> str:
        """Start GrokBot/Hand OAuth. Returns a Google URL; completion is via /oauth/callback."""
        result = await accounts_mod.accounts_auth_start()
        return json.dumps(result, indent=2)

    if not http:

        @mcp.tool()
        async def accounts_add() -> str:
            """Connect a Gmail account via local loopback OAuth (stdio only)."""
            result = await accounts_mod.accounts_add()
            return json.dumps(result, indent=2)

        @mcp.tool()
        async def accounts_remove(account: str) -> str:
            """Remove a connected Gmail account and revoke its token at Google."""
            result = await accounts_mod.accounts_remove(account)
            return json.dumps(result, indent=2)

    @mcp.tool()
    async def send(
        account: str,
        to: str,
        subject: str,
        idempotency_key: str,
        body: str = "",
        html_body: str = "",
        attachments_json: str = "[]",
        footer: str = "",
        cc: str = "",
    ) -> str:
        """Send new mail. Attachments are outbox file paths only. Returns proof payload."""
        result = await mail_mod.send(
            account=account,
            to=to,
            subject=subject,
            idempotency_key=idempotency_key,
            body=body,
            html_body=html_body,
            attachments=_parse_attachments(attachments_json),
            footer=footer,
            cc=cc,
        )
        return mail_mod.format_result(result)

    @mcp.tool()
    async def reply(
        account: str,
        message_id: str,
        idempotency_key: str,
        body: str = "",
        html_body: str = "",
        attachments_json: str = "[]",
        footer: str = "",
        subject: str = "",
    ) -> str:
        """Reply on a thread. Same attachment and proof rules as send."""
        result = await mail_mod.reply(
            account=account,
            message_id=message_id,
            idempotency_key=idempotency_key,
            body=body,
            html_body=html_body,
            attachments=_parse_attachments(attachments_json),
            footer=footer,
            subject=subject,
        )
        return mail_mod.format_result(result)

    @mcp.tool()
    async def forward(
        account: str,
        message_id: str,
        to: str,
        idempotency_key: str,
        body: str = "",
        html_body: str = "",
        attachments_json: str = "[]",
        footer: str = "",
        subject: str = "",
    ) -> str:
        """Forward a message on-thread. Same attachment and proof rules as send."""
        result = await mail_mod.forward(
            account=account,
            message_id=message_id,
            to=to,
            idempotency_key=idempotency_key,
            body=body,
            html_body=html_body,
            attachments=_parse_attachments(attachments_json),
            footer=footer,
            subject=subject,
        )
        return mail_mod.format_result(result)

    @mcp.tool()
    async def search(
        account: str,
        query: str,
        max_results: int = 25,
        page_token: str = "",
    ) -> str:
        """Search Gmail threads using Gmail query syntax."""
        return inbox_mod.format_result(
            await inbox_mod.search(account, query, max_results=max_results, page_token=page_token)
        )

    @mcp.tool()
    async def get_thread(account: str, thread_id: str, format: str = "plain") -> str:
        """Get messages on a thread. format=full includes HTML and attachment metadata."""
        return inbox_mod.format_result(
            await inbox_mod.get_thread_messages(account, thread_id, format=format)
        )

    @mcp.tool()
    async def get_message(account: str, message_id: str, format: str = "plain") -> str:
        """Get one message. format=full includes HTML and attachment metadata."""
        return inbox_mod.format_result(
            await inbox_mod.get_message_detail(account, message_id, format=format)
        )

    @mcp.tool()
    async def get_attachment(
        account: str,
        message_id: str,
        attachment_id: str,
        output_path: str,
    ) -> str:
        """Write an attachment under download_root. Returns path and byte size."""
        return inbox_mod.format_result(
            await inbox_mod.get_attachment_file(account, message_id, attachment_id, output_path)
        )

    @mcp.tool()
    async def labels_list(account: str) -> str:
        """List system and user labels for an account."""
        return inbox_mod.format_result(await inbox_mod.labels_list(account))

    @mcp.tool()
    async def labels_create(account: str, name: str) -> str:
        """Create a user label."""
        return inbox_mod.format_result(await inbox_mod.labels_create(account, name))

    @mcp.tool()
    async def label(account: str, thread_id: str, labels: str) -> str:
        """Add labels to a thread (comma-separated names or ids)."""
        return inbox_mod.format_result(await inbox_mod.label(account, thread_id, labels))

    @mcp.tool()
    async def unlabel(account: str, thread_id: str, labels: str) -> str:
        """Remove labels from a thread (comma-separated names or ids)."""
        return inbox_mod.format_result(await inbox_mod.unlabel(account, thread_id, labels))

    @mcp.tool()
    async def archive(account: str, thread_id: str) -> str:
        """Remove INBOX from a thread."""
        return inbox_mod.format_result(await inbox_mod.archive(account, thread_id))

    @mcp.tool()
    async def trash(account: str, thread_id: str) -> str:
        """Move a thread to trash."""
        return inbox_mod.format_result(await inbox_mod.trash(account, thread_id))

    @mcp.tool()
    async def untrash(account: str, thread_id: str) -> str:
        """Restore a thread from trash."""
        return inbox_mod.format_result(await inbox_mod.untrash(account, thread_id))

    @mcp.tool()
    async def draft_create(
        account: str,
        to: str,
        subject: str,
        body: str = "",
        html_body: str = "",
        attachments_json: str = "[]",
        footer: str = "",
        cc: str = "",
        thread_id: str = "",
    ) -> str:
        """Create a draft with the same MIME rules as send."""
        return inbox_mod.format_result(
            await inbox_mod.draft_create(
                account=account,
                to=to,
                subject=subject,
                body=body,
                html_body=html_body,
                attachments=_parse_attachments(attachments_json),
                footer=footer,
                cc=cc,
                thread_id=thread_id,
            )
        )

    @mcp.tool()
    async def draft_send(account: str, draft_id: str, idempotency_key: str) -> str:
        """Send a draft with post-send proof."""
        return inbox_mod.format_result(
            await inbox_mod.draft_send(account, draft_id, idempotency_key)
        )

    if http:
        registered = {t.name for t in mcp._tool_manager.list_tools()}
        extra = registered - HTTP_TOOL_NAMES
        missing = HTTP_TOOL_NAMES - registered
        if extra or missing:
            raise RuntimeError(f"HTTP tool allow-list mismatch: extra={extra} missing={missing}")

    return mcp

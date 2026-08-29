"""MCPServer factory — stdio (all tools) vs HTTP (Hand allow-list)."""

from __future__ import annotations

import json
import secrets

from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from pigeon_mcp import accounts as accounts_mod
from pigeon_mcp import identities as identities_mod
from pigeon_mcp import inbox as inbox_mod
from pigeon_mcp import mail as mail_mod
from pigeon_mcp.attachments import MAX_TOTAL_BYTES, stage_outbox_bytes
from pigeon_mcp.bearer_auth import StaticBearerVerifier
from pigeon_mcp.config import http_public_base_url, settings

VERSION = "0.1.0"

# Hand / gateway may call these over HTTP.
HTTP_TOOL_NAMES = frozenset(
    {
        "gmail_status",
        "accounts_list",
        "accounts_auth_start",
        "identities_list",
        "search",
        "messages_list",
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
            raise RuntimeError("PIGEON_MCP_HTTP_BEARER_TOKEN is required for HTTP transport")
        # Static bearer via connector headers only. Do not publish OAuth AS/PRM on the
        # public internet — Hand Authenticate UI belongs behind Cloudflare Access later.
        public_base = http_public_base_url()
        auth = AuthSettings(
            issuer_url=public_base,
            resource_server_url=None,
        )
        mcp = MCPServer(
            "pigeon-mcp",
            version=VERSION,
            auth=auth,
            token_verifier=StaticBearerVerifier(settings.http_bearer_token),
        )
    else:
        mcp = MCPServer("pigeon-mcp", version=VERSION)

    if http:

        def _bearer_ok(request: Request) -> bool:
            """custom_route skips MCP auth — enforce the static bearer ourselves."""
            expected = settings.http_bearer_token
            if not expected:
                return False
            header = request.headers.get("authorization", "")
            if not header.lower().startswith("bearer "):
                return False
            got = header[7:].strip()
            if len(got) != len(expected):
                return False
            return secrets.compare_digest(got, expected)

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

        @mcp.custom_route("/healthz", methods=["GET"])
        async def healthz(_request: Request) -> Response:
            """Unauthenticated liveness for watchdogs (curl -sf). No secrets/version."""
            return PlainTextResponse("ok", status_code=200)

        @mcp.custom_route("/outbox/stage", methods=["POST"])
        async def outbox_stage(request: Request) -> Response:
            """Stage a file under outbox_root for later send/reply/forward (bearer required)."""
            if not _bearer_ok(request):
                return JSONResponse(
                    {"error": "invalid_token", "error_description": "Authentication required"},
                    status_code=401,
                )
            content_type = (request.headers.get("content-type") or "").lower()
            try:
                if "multipart/form-data" in content_type:
                    form = await request.form()
                    upload = form.get("file")
                    if upload is None:
                        return JSONResponse({"error": "file field required"}, status_code=400)
                    filename = getattr(upload, "filename", None) or form.get("filename") or "attachment.bin"
                    if hasattr(upload, "read"):
                        data = await upload.read()
                    else:
                        return JSONResponse({"error": "file field required"}, status_code=400)
                    overwrite = str(form.get("overwrite", "")).lower() in {"1", "true", "yes"}
                else:
                    # Raw body + filename query/header for simple agent clients
                    filename = (
                        request.query_params.get("filename")
                        or request.headers.get("x-filename")
                        or "attachment.bin"
                    )
                    data = await request.body()
                    overwrite = request.query_params.get("overwrite", "").lower() in {
                        "1",
                        "true",
                        "yes",
                    }
                if not data:
                    return JSONResponse({"error": "empty body"}, status_code=400)
                if len(data) > MAX_TOTAL_BYTES:
                    return JSONResponse(
                        {"error": f"file exceeds {MAX_TOTAL_BYTES} bytes"},
                        status_code=413,
                    )
                path = stage_outbox_bytes(
                    settings.outbox_root,
                    filename=str(filename),
                    data=data,
                    overwrite=overwrite,
                )
            except ValueError as exc:
                return JSONResponse({"error": str(exc)}, status_code=400)
            except Exception as exc:
                return JSONResponse({"error": f"stage failed: {exc}"}, status_code=500)
            return JSONResponse(
                {
                    "path": str(path),
                    "filename": path.name,
                    "size": path.stat().st_size,
                    "outbox_root": str(settings.outbox_root.expanduser().resolve()),
                },
                status_code=201,
            )

    @mcp.tool()
    async def gmail_status() -> str:
        """Report server version and configuration (no Gmail API calls)."""
        accts = await accounts_mod.accounts_list()
        return (
            f"pigeon-mcp {VERSION}\n"
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

    @mcp.tool()
    async def identities_list(account: str) -> str:
        """Verified send-as identities for an account. Only these may be used as from_identity."""
        return json.dumps(await identities_mod.list_identities(account), indent=2)

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
        from_identity: str = "",
    ) -> str:
        """Send new mail. Attachments are outbox file paths only. Returns proof payload.

        from_identity: optional verified send-as address (see identities_list). Sets From
        with its display name and Reply-To. Empty = the account address itself.
        """
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
            from_identity=from_identity,
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
        from_identity: str = "",
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
            from_identity=from_identity,
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
        from_identity: str = "",
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
            from_identity=from_identity,
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
    async def messages_list(
        account: str,
        query: str,
        max_results: int = 25,
        page_token: str = "",
    ) -> str:
        """List messages (not threads) with headers only — no bodies. Use for routing
        sweeps: originalTo is the real recipient behind a catch-all; authResults carries
        dkim/dmarc. Fetch bodies afterwards with get_message only where needed."""
        return inbox_mod.format_result(
            await inbox_mod.messages_list(
                account, query, max_results=max_results, page_token=page_token
            )
        )

    @mcp.tool()
    async def get_thread(account: str, thread_id: str, format: str = "plain") -> str:
        """Get messages on a thread. format=metadata is headers+snippet only (cheap);
        plain adds the text body; full adds HTML and attachment metadata."""
        return inbox_mod.format_result(
            await inbox_mod.get_thread_messages(account, thread_id, format=format)
        )

    @mcp.tool()
    async def get_message(account: str, message_id: str, format: str = "plain") -> str:
        """Get one message. format=metadata is headers+snippet only (cheap); plain adds
        the text body; full adds HTML and attachment metadata."""
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
        from_identity: str = "",
    ) -> str:
        """Create a draft with the same MIME rules as send (from_identity as in send)."""
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
                from_identity=from_identity,
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

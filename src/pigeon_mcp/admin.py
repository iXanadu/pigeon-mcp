"""Owner dashboard routes under /~/ — passkey session, not MCP bearer."""

from __future__ import annotations

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

from pigeon_mcp.admin_page import ADMIN_HTML
from pigeon_mcp.config import http_public_base_url
from pigeon_mcp.passkeys import PasskeyError, login_begin, login_finish, register_begin, register_finish
from pigeon_mcp.tenants import get_store

COOKIE = "pigeon_s"
SETUP_COOKIE = "pigeon_setup"


def _secure() -> bool:
    return http_public_base_url().startswith("https://")


def _set_cookie(resp: Response, name: str, value: str, max_age: int) -> None:
    resp.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        secure=_secure(),
        samesite="lax",
        path="/~",
    )


def _clear_cookie(resp: Response, name: str) -> None:
    resp.delete_cookie(name, path="/~")


def _session(request: Request):
    return get_store().resolve_session(request.cookies.get(COOKIE, ""))


def _json_error(status: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


async def _body(request: Request) -> dict:
    try:
        data = await request.json()
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def mount_admin(mcp) -> None:
    @mcp.custom_route("/~", methods=["GET"])
    @mcp.custom_route("/~/", methods=["GET"])
    async def admin_home(_request: Request) -> Response:
        return HTMLResponse(ADMIN_HTML)

    @mcp.custom_route("/~/setup", methods=["GET"])
    async def admin_setup(request: Request) -> Response:
        token = request.query_params.get("t") or ""
        store = get_store()
        resp = HTMLResponse(ADMIN_HTML)
        if token and store.setup_token_ok(token):
            _set_cookie(resp, SETUP_COOKIE, token, max_age=1800)
        return resp

    @mcp.custom_route("/~/api/bootstrap-state", methods=["GET"])
    async def bootstrap_state(request: Request) -> Response:
        store = get_store()
        setup = request.cookies.get(SETUP_COOKIE, "")
        return JSONResponse(
            {
                "needsSetup": not store.has_passkey(),
                "setupOk": bool(setup) and store.setup_token_ok(setup),
                "hasPasskey": store.has_passkey(),
            }
        )

    @mcp.custom_route("/~/api/me", methods=["GET"])
    async def me(request: Request) -> Response:
        sess = _session(request)
        if not sess or sess.purpose != "full":
            return _json_error(401, "Sign in first.")
        return JSONResponse({"ok": True, "userId": sess.user_id})

    @mcp.custom_route("/~/api/login/begin", methods=["POST"])
    async def api_login_begin(_request: Request) -> Response:
        return JSONResponse(login_begin(get_store()))

    @mcp.custom_route("/~/api/login/finish", methods=["POST"])
    async def api_login_finish(request: Request) -> Response:
        body = await _body(request)
        try:
            secret = login_finish(get_store(), body.get("credential") or {})
        except PasskeyError as exc:
            return _json_error(exc.status, exc.message)
        resp = JSONResponse({"ok": True})
        _set_cookie(resp, COOKIE, secret, max_age=30 * 24 * 3600)
        return resp

    @mcp.custom_route("/~/api/register/begin", methods=["POST"])
    async def api_register_begin(request: Request) -> Response:
        store = get_store()
        sess = _session(request)
        setup = request.cookies.get(SETUP_COOKIE, "")
        if sess and sess.purpose == "full":
            user_id = sess.user_id
        elif setup and store.setup_token_ok(setup) and not store.has_passkey():
            user_id = store.ensure_root()
        else:
            return _json_error(401, "Sign in first, or open a fresh setup link.")
        try:
            return JSONResponse(register_begin(store, user_id))
        except PasskeyError as exc:
            return _json_error(exc.status, exc.message)

    @mcp.custom_route("/~/api/register/finish", methods=["POST"])
    async def api_register_finish(request: Request) -> Response:
        store = get_store()
        body = await _body(request)
        sess = _session(request)
        setup = request.cookies.get(SETUP_COOKIE, "")
        if sess and sess.purpose == "full":
            user_id = sess.user_id
            consume = False
        elif setup and store.setup_token_ok(setup) and not store.has_passkey():
            user_id = store.ensure_root()
            consume = True
        else:
            return _json_error(401, "Sign in first, or open a fresh setup link.")
        try:
            pid = register_finish(store, user_id, body.get("credential") or {}, body.get("name") or "")
        except PasskeyError as exc:
            return _json_error(exc.status, exc.message)
        if consume:
            store.consume_setup_token(setup)
        resp = JSONResponse({"ok": True, "id": pid})
        if consume or not sess:
            cookie = store.create_session(user_id, purpose="full")
            _set_cookie(resp, COOKIE, cookie, max_age=30 * 24 * 3600)
            _clear_cookie(resp, SETUP_COOKIE)
        return resp

    @mcp.custom_route("/~/api/logout", methods=["POST"])
    async def api_logout(_request: Request) -> Response:
        resp = JSONResponse({"ok": True})
        _clear_cookie(resp, COOKIE)
        return resp

    @mcp.custom_route("/~/api/tenants", methods=["GET"])
    async def api_tenants_list(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        return JSONResponse({"items": get_store().list_tenants()})

    @mcp.custom_route("/~/api/tenants", methods=["POST"])
    async def api_tenants_create(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        body = await _body(request)
        try:
            _tid, secret = get_store().create_tenant(
                body.get("name") or "",
                can_auth_start=bool(body.get("canAuthStart")),
            )
        except ValueError as exc:
            return _json_error(422, str(exc))
        return JSONResponse({"token": secret})

    @mcp.custom_route("/~/api/tenants/revoke", methods=["POST"])
    async def api_tenants_revoke(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        body = await _body(request)
        get_store().revoke_tenant(body.get("tenantId") or "")
        return JSONResponse({"ok": True})

    @mcp.custom_route("/~/api/grants", methods=["POST"])
    async def api_grants_add(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        body = await _body(request)
        try:
            get_store().grant(body.get("tenantId") or "", body.get("account") or "")
        except ValueError as exc:
            return _json_error(422, str(exc))
        return JSONResponse({"ok": True})

    @mcp.custom_route("/~/api/grants", methods=["DELETE"])
    async def api_grants_del(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        body = await _body(request)
        get_store().revoke_grant(body.get("tenantId") or "", body.get("account") or "")
        return JSONResponse({"ok": True})

    @mcp.custom_route("/~/api/accounts", methods=["GET"])
    async def api_accounts(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        from pigeon_mcp import accounts as accounts_mod

        rows = await accounts_mod.accounts_list(unrestricted=True)
        return JSONResponse({"items": rows})

    @mcp.custom_route("/~/api/audit", methods=["GET"])
    async def api_audit(request: Request) -> Response:
        if not _session(request):
            return _json_error(401, "Sign in first.")
        return JSONResponse({"items": get_store().list_audit()})


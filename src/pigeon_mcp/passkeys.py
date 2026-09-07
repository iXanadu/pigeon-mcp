"""WebAuthn register/login for the owner dashboard. Challenges live in SQLite."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, options_to_json_dict
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from pigeon_mcp.config import http_public_base_url, settings
from pigeon_mcp.tenant_store import TenantStore


class PasskeyError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def _rp_id() -> str:
    parsed = urlparse(http_public_base_url())
    host = (parsed.hostname or "localhost").split(":")[0]
    return host


def _origin() -> str:
    parsed = urlparse(http_public_base_url())
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return f"http://{settings.http_host}:{settings.http_port}"


def _challenge_from_client_data(credential: dict) -> str | None:
    import base64

    raw = credential.get("response", {}).get("clientDataJSON")
    if not raw:
        return None
    pad = "=" * (-len(raw) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(raw + pad))
    except Exception:
        return None
    return data.get("challenge")


def login_begin(store: TenantStore) -> dict:
    options = generate_authentication_options(
        rp_id=_rp_id(),
        timeout=120000,
        allow_credentials=[],
        user_verification=UserVerificationRequirement.PREFERRED,
    )
    store.put_challenge(bytes_to_base64url(options.challenge), {"kind": "login"})
    return {"publicKey": options_to_json_dict(options)}


def login_finish(store: TenantStore, credential: dict) -> str:
    challenge_b64 = _challenge_from_client_data(credential)
    if not challenge_b64:
        raise PasskeyError(401, "That sign-in could not be verified.")
    stored = store.pop_challenge(challenge_b64)
    if not stored or stored.get("kind") != "login":
        raise PasskeyError(401, "That sign-in could not be verified.")
    cred_id = credential.get("id") or credential.get("rawId")
    if not cred_id:
        raise PasskeyError(401, "That passkey is not registered here.")
    try:
        cred_bytes = base64url_to_bytes(cred_id)
    except Exception as exc:
        raise PasskeyError(401, "That passkey is not registered here.") from exc
    row = store.passkey_by_credential_id(cred_bytes)
    if row is None:
        raise PasskeyError(401, "That passkey is not registered here.")
    try:
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            credential_public_key=row["public_key"],
            credential_current_sign_count=row["sign_count"],
            require_user_verification=False,
        )
    except Exception as exc:
        raise PasskeyError(401, "That sign-in could not be verified.") from exc
    if row["sign_count"] and verification.new_sign_count <= row["sign_count"]:
        raise PasskeyError(401, "That passkey may have been copied. Sign-in was refused.")
    store.update_passkey_count(row["id"], verification.new_sign_count)
    return store.create_session(row["user_id"], purpose="full")


def register_begin(store: TenantStore, user_id: str) -> dict:
    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name="Pigeon",
        user_name="owner",
        user_id=user_id.encode(),
        user_display_name="Owner",
        timeout=120000,
        attestation=AttestationConveyancePreference.NONE,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
    )
    store.put_challenge(
        bytes_to_base64url(options.challenge),
        {"kind": "register", "user_id": user_id},
    )
    return {"publicKey": options_to_json_dict(options)}


def register_finish(store: TenantStore, user_id: str, credential: dict, name: str) -> str:
    challenge_b64 = _challenge_from_client_data(credential)
    if not challenge_b64:
        raise PasskeyError(401, "That registration could not be verified.")
    stored = store.pop_challenge(challenge_b64)
    if not stored or stored.get("kind") != "register" or stored.get("user_id") != user_id:
        raise PasskeyError(401, "That registration could not be verified.")
    try:
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_rp_id=_rp_id(),
            expected_origin=_origin(),
            require_user_verification=False,
        )
    except Exception as exc:
        raise PasskeyError(401, "That registration could not be verified.") from exc
    return store.add_passkey(
        user_id=user_id,
        credential_id=verification.credential_id,
        public_key=verification.credential_public_key,
        sign_count=verification.sign_count,
        name=(name or "").strip() or "Passkey",
    )

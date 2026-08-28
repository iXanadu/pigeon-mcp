from pathlib import Path
from urllib.parse import urlparse

import os

from mcp.server.transport_security import TransportSecuritySettings
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"
_KEYS_FILE = _REPO_ROOT / ".keys"


def _dotenv_files() -> tuple[Path, ...] | None:
    """Paths that exist — never pass None into pydantic-settings (env-only deploy)."""
    files = tuple(p for p in (_ENV_FILE, _KEYS_FILE) if p.is_file())
    return files or None


class Settings(BaseSettings):
    """Non-secret config from .env; secrets from .keys (both override via process env)."""

    environment: str = "local"
    log_level: str = "info"

    # HTTP transport (remote MCP clients via gateway)
    http_host: str = "127.0.0.1"
    http_port: int = 8879
    # Public URL Hand/gateway uses (defaults from oauth_public_redirect_uri origin)
    http_public_url: str = ""
    http_bearer_token: str = ""

    # Attachment outbox — only paths under this root are accepted for send
    outbox_root: Path = Path.home() / "Outbox"

    # Download root — get_attachment may only write under this tree
    download_root: Path = Path.home() / "Inbox"

    # OAuth token storage (populated after accounts.add)
    tokens_dir: Path = Path.home() / ".config" / "pigeon-mcp" / "tokens"

    # Google OAuth client — Desktop for stdio; optional Web slots for Hand/public callback
    google_client_id: str = ""
    google_client_secret: str = ""
    google_web_client_id: str = ""
    google_web_client_secret: str = ""

    # OAuth loopback callback (Desktop / stdio accounts_add)
    oauth_redirect_uri: str = "http://127.0.0.1:8767/oauth/callback"

    # Public HTTPS callback for Hand-initiated consent (Web application client).
    # REQUIRED for accounts_auth_start — no fleet hostname default in public code.
    oauth_public_redirect_uri: str = ""

    model_config = SettingsConfigDict(
        env_prefix="PIGEON_MCP_",
        env_file=_dotenv_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("outbox_root", "download_root", "tokens_dir", mode="before")
    @classmethod
    def _expand_user_path(cls, value: object) -> Path:
        if isinstance(value, str):
            value = Path(value)
        if not isinstance(value, Path):
            raise TypeError("path must be str or Path")
        return value.expanduser()


settings = Settings()


def ensure_data_dirs() -> None:
    """Create storage dirs on every startup; chmod 0700 unconditionally (self-heal /tmp wipe)."""
    for path in (settings.outbox_root, settings.download_root, settings.tokens_dir):
        p = path.expanduser()
        p.mkdir(parents=True, exist_ok=True)
        resolved = p.resolve()
        if not resolved.is_dir():
            raise RuntimeError(f"storage path is not a directory: {resolved}")
        resolved.chmod(0o700)
        if not os.access(resolved, os.W_OK):
            raise RuntimeError(f"storage path not writable: {resolved}")
        parent = resolved.parent
        # /tmp is 1777 — mkdir leaves 775; chmod parent so attachments aren't listable.
        if str(parent).startswith(("/tmp/", "/private/tmp/")) and parent.is_dir():
            parent.chmod(0o700)


def http_public_base_url(cfg: Settings | None = None) -> str:
    """Origin remote MCP clients reach — not the local bind address."""
    cfg = cfg or settings
    explicit = cfg.http_public_url.strip()
    if explicit:
        return explicit.rstrip("/")
    public_redirect = cfg.oauth_public_redirect_uri.strip()
    if public_redirect:
        parsed = urlparse(public_redirect)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return f"http://{cfg.http_host}:{cfg.http_port}"


def http_transport_security(cfg: Settings | None = None) -> TransportSecuritySettings | None:
    """Allow-list public Host/Origin when behind a reverse proxy (SDK default is loopback-only)."""
    cfg = cfg or settings
    if not cfg.http_public_url.strip() and not cfg.oauth_public_redirect_uri.strip():
        return None

    local = f"http://{cfg.http_host}:{cfg.http_port}".rstrip("/")
    public = http_public_base_url(cfg).rstrip("/")
    if public == local:
        return None

    parsed = urlparse(public)
    if not parsed.scheme or not parsed.netloc:
        return None

    hostname = parsed.hostname or parsed.netloc.split(":")[0]
    allowed_hosts = [hostname, f"{hostname}:*"]
    if parsed.netloc not in allowed_hosts:
        allowed_hosts.append(parsed.netloc)

    origin = f"{parsed.scheme}://{hostname}"
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=allowed_hosts,
        allowed_origins=[origin, f"{origin}:*"],
    )

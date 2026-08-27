from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ENV_FILE = _REPO_ROOT / ".env"
_KEYS_FILE = _REPO_ROOT / ".keys"


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
    tokens_dir: Path = Path.home() / ".config" / "gmail-mcp" / "tokens"

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
        env_prefix="GMAIL_MCP_",
        env_file=(_ENV_FILE if _ENV_FILE.is_file() else None, _KEYS_FILE if _KEYS_FILE.is_file() else None),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def http_public_base_url() -> str:
    """Origin remote MCP clients reach — not the local bind address."""
    explicit = settings.http_public_url.strip()
    if explicit:
        return explicit.rstrip("/")
    public_redirect = settings.oauth_public_redirect_uri.strip()
    if public_redirect:
        parsed = urlparse(public_redirect)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return f"http://{settings.http_host}:{settings.http_port}"

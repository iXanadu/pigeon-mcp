"""Gmail MCP Streamable HTTP entrypoint — bearer auth, Hand tool allow-list."""

import asyncio
import logging

from pigeon_mcp.app import build_mcp
from pigeon_mcp.attachments import sweep_old_files
from pigeon_mcp.config import admin_db_path, ensure_data_dirs, http_transport_security, settings

log = logging.getLogger(__name__)
SWEEP_EVERY_SECONDS = 3600


def sweep_file_roots() -> int:
    """One pass over outbox + download roots. Returns files removed."""
    if settings.file_ttl_hours <= 0:
        return 0
    max_age = settings.file_ttl_hours * 3600
    protect = (settings.tokens_dir, admin_db_path())
    removed = 0
    for root in (settings.outbox_root, settings.download_root):
        removed += sweep_old_files(root, max_age, protect=protect)
    return removed


async def _sweep_forever() -> None:
    # Hourly keeps every file within TTL + 1h of its write.
    while True:
        try:
            removed = await asyncio.to_thread(sweep_file_roots)
            if removed:
                log.info("file sweep removed %d file(s) older than %dh", removed, settings.file_ttl_hours)
        except Exception:
            log.exception("file sweep failed")
        await asyncio.sleep(SWEEP_EVERY_SECONDS)


async def _amain() -> None:
    ensure_data_dirs()
    mcp = build_mcp(http=True)
    sweeper = asyncio.create_task(_sweep_forever())
    try:
        await mcp.run_streamable_http_async(
            host=settings.http_host,
            port=settings.http_port,
            streamable_http_path="/mcp",
            transport_security=http_transport_security(),
        )
    finally:
        sweeper.cancel()


def main() -> None:
    asyncio.run(_amain())


if __name__ == "__main__":
    main()

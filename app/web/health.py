from __future__ import annotations

import logging

from aiohttp import web

logger = logging.getLogger(__name__)


def create_health_app(
    tts_status_fn, db_ping_fn, extra: dict[str, str] | None = None
) -> web.Application:
    """tts_status_fn: () -> bool (sync). db_ping_fn: () -> bool (async)."""

    async def health(_request: web.Request) -> web.Response:
        tts = False
        try:
            tts = bool(tts_status_fn())
        except Exception:  # noqa: BLE001
            logger.exception("tts status check failed")
        database = False
        try:
            database = await db_ping_fn()
        except Exception:  # noqa: BLE001
            logger.exception("db ping failed")
        body: dict[str, object] = {"status": "ok", "tts": tts, "database": database}
        if extra:
            body.update(extra)  # only non-secret metadata
        return web.json_response(body, status=200 if (tts and database) else 503)

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", lambda _r: web.json_response({"service": "wioos-witness"}))
    return app


async def start_health_server(app: web.Application, port: int) -> web.AppRunner:
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info("Health server listening on 0.0.0.0:%s", port)
    return runner

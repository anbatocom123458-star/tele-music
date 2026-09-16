"""Process entrypoint: Telegram bot (long polling) + /health HTTP server.

Boot order:
1. Load ENV config (fail fast).
2. Connect ChromaDB, ensure collections, seed redeem codes (hashed).
3. Download/cache TTS models (skips already-cached files).
4. Reset stale PROCESSING states (Railway restart recovery).
5. Start health server, start job workers, start polling.
"""
from __future__ import annotations

import asyncio
import logging

from telegram.ext import ApplicationBuilder

from app.ai.client import AIClient
from app.bot.handlers import register_handlers
from app.bot.keyboards import RateLimiter
from app.bot.state import Services
from app.config import ConfigError, load_config
from app.database.chroma import Database
from app.database.conversations import ConversationStore, MessageStore
from app.database.redeem import RedeemStore
from app.database.usage import (
    SvgGenerationStore,
    UsageStore,
    VoiceGenerationStore,
)
from app.database.users import UserStore
from app.logging_setup import setup_logging
from app.tts.engine import TTSEngine, cleanup_dir
from app.web.health import create_health_app, start_health_server
from app.workers.queue import JobManager

logger = logging.getLogger("wioos")


async def main() -> None:
    try:
        cfg = load_config()
    except ConfigError as exc:
        print(f"FATAL: {exc}", flush=True)
        raise SystemExit(1) from exc

    setup_logging(
        secrets=[
            cfg.telegram_bot_token,
            cfg.ai_api_key,
            cfg.chroma.apikey,
            cfg.chroma.secret,
            *[c for c in cfg.redeem_codes.values()],
        ]
    )
    logger.info("Booting Wioos Witness bot (model_dir=%s, port=%s)", cfg.model_dir, cfg.port)

    # 1. Database
    db = Database(cfg.chroma)
    await db.connect()

    # 2. Stores / services
    users = UserStore(db)
    redeem = RedeemStore(db, users, initial_credit=cfg.initial_credit)
    conversations = ConversationStore(db)
    messages = MessageStore(db)
    usage = UsageStore(db)
    voice_gens = VoiceGenerationStore(db)
    svg_gens = SvgGenerationStore(db)
    tts = TTSEngine(cfg)
    ai = AIClient(cfg)
    jobs = JobManager(cfg.limits)
    services = Services(
        cfg=cfg, db=db, users=users, redeem=redeem, conversations=conversations,
        messages=messages, usage=usage, voice_gens=voice_gens, svg_gens=svg_gens,
        tts=tts, ai=ai, jobs=jobs, limiter=RateLimiter(cfg.limits),
    )

    # 3. Seed redeem codes (plaintext is consumed & dropped from memory)
    seeded = await redeem.seed(cfg.consume_redeem_codes())
    logger.info("Redeem codes seeded: %d new", seeded)

    # 4. TTS models (download at container start, cached on disk)
    try:
        await tts.ensure_models_downloaded()
    except Exception as exc:  # noqa: BLE001
        logger.error("TTS model download failed: %s — bot will serve SVG only until models are available", exc)

    # 5. Railway restart recovery: clear stale PROCESSING states
    try:
        reset = await users.reset_processing_states()
        if reset:
            logger.info("Reset %d stale PROCESSING user states after restart", reset)
    except Exception:  # noqa: BLE001
        logger.exception("state recovery failed")

    # 6. Health server
    health_app = create_health_app(tts.status, db.ping)
    runner = await start_health_server(health_app, cfg.port)

    # 7. Temp dirs
    for path in (cfg.tmp_voice_dir, cfg.tmp_svg_dir):
        try:
            cleanup_dir(path)
        except Exception:  # noqa: BLE001
            pass

    # 8. Telegram bot
    app = ApplicationBuilder().token(cfg.telegram_bot_token).post_init(_post_init(services)).build()
    register_handlers(app)

    logger.info("Starting poll loop")
    try:
        await app.initialize()
        await jobs.start()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()  # run forever
    finally:
        await app.updater.stop()
        await app.stop()
        await jobs.stop()
        await ai.close()
        await runner.cleanup()
        await app.shutdown()


def _post_init(services: Services):
    async def _setup(application) -> None:
        await application.bot.set_my_commands(
            [
                ("start", "Bắt đầu / hướng dẫn"),
                ("redeem", "Nhập mã kích hoạt"),
                ("acc", "Xem tài khoản"),
                ("new", "Tạo cuộc trò chuyện mới"),
                ("voice", "Tạo giọng nói"),
                ("svg", "Tạo SVG"),
                ("history", "Xem lịch sử"),
            ]
        )
        logger.info("Bot commands registered")

    return _setup


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

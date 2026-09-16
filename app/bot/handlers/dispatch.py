"""Routes plain text by the user's persisted state (state machine, spec §20).

A stray text with state IDLE is NEVER treated as a voice/svg request — the
user must explicitly enter a workflow first.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers import svg, voice
from app.bot.handlers.common import ensure_user, services
from app.bot.messages import PROCESSING_NOTE, STRAY_TEXT
from app.database.users import (
    PROCESSING_STATES,
    STATE_SVG_WAITING_PROMPT,
    STATE_VOICE_WAITING_TEXT,
)

logger = logging.getLogger(__name__)


async def route_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    try:
        user = await ensure_user(update, svc)
    except Exception:  # noqa: BLE001
        logger.exception("route_text: db unavailable")
        return

    state = user.get("state")
    if state == STATE_VOICE_WAITING_TEXT:
        await voice.handle_voice_text(update, ctx, user)
    elif state == STATE_SVG_WAITING_PROMPT:
        await svg.handle_svg_prompt(update, ctx, user)
    elif state in PROCESSING_STATES:
        await update.effective_message.reply_text(PROCESSING_NOTE)
    else:
        await update.effective_message.reply_text(STRAY_TEXT)

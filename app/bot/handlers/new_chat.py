"""/new — create a fresh conversation."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import ensure_user, require_activated, services
from app.bot.keyboards import menu_kb
from app.bot.messages import GENERIC_DOWN, NEW_CHAT_TEXT
from app.database.chroma import Database
from app.database.users import STATE_IDLE

logger = logging.getLogger(__name__)


async def new_chat(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    user = await ensure_user(update, svc)
    if not await require_activated(update, user):
        return
    try:
        conv = await svc.conversations.create(update.effective_user.id)
        await svc.users.set_fields(
            update.effective_user.id,
            active_conversation=conv["conversation_id"],
            state=STATE_IDLE,
            pending_text="",
            pending_voice="",
        )
    except Exception:  # noqa: BLE001
        logger.exception("new_chat failed")
        await update.effective_message.reply_text(GENERIC_DOWN)
        return
    await update.effective_message.reply_text(
        NEW_CHAT_TEXT.format(cid=conv["conversation_id"]), reply_markup=menu_kb()
    )

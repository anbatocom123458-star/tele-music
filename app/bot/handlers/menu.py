"""Main menu + cancel callbacks."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers import account, history, new_chat, svg, voice
from app.bot.handlers.common import ensure_user, services
from app.bot.messages import VOICE_CANCELLED
from app.database.users import STATE_IDLE

logger = logging.getLogger(__name__)


async def handle_menu_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data or ""
    await handle_menu(update, ctx, data.split(":", 1)[-1])


async def handle_cancel_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data or ""
    await handle_cancel(update, ctx, data.split(":", 1)[-1])


async def handle_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    query = update.callback_query
    await query.answer()
    fake_update = update
    if action == "voice":
        await voice.voice_command(fake_update, ctx)
    elif action == "svg":
        await svg.svg_command(fake_update, ctx)
    elif action == "new":
        await new_chat.new_chat(fake_update, ctx)
    elif action == "acc":
        await account.acc(fake_update, ctx)
    elif action == "history":
        await history.history(fake_update, ctx)


async def handle_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE, scope: str) -> None:
    query = update.callback_query
    svc = services(ctx)
    uid = update.effective_user.id
    await query.answer()
    try:
        await svc.users.set_fields(uid, state=STATE_IDLE, pending_text="", pending_voice="")
    except Exception:  # noqa: BLE001
        logger.exception("cancel: reset state failed")
    try:
        await query.edit_message_text(VOICE_CANCELLED if scope == "voice" else "✅ Đã đóng.")
    except Exception:  # noqa: BLE001
        pass

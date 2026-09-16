"""/start and /help."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import ensure_user, services
from app.bot.keyboards import menu_kb
from app.bot.messages import START_TEXT

logger = logging.getLogger(__name__)


async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user or not update.effective_message:
        return
    svc = services(ctx)
    try:
        await ensure_user(update, svc)
    except Exception:  # noqa: BLE001
        logger.exception("start: ensure_user failed")
    await update.effective_message.reply_text(START_TEXT, reply_markup=menu_kb())


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_message:
        await update.effective_message.reply_text(START_TEXT, reply_markup=menu_kb())

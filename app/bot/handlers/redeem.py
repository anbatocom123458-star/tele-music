"""/redeem CODE"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import ensure_user, fmt_usd, services
from app.bot.keyboards import menu_kb
from app.bot.messages import (
    REDEEM_ALREADY,
    REDEEM_INVALID,
    REDEEM_OK,
    REDEEM_USAGE,
    REDEEM_USED,
)
from app.database.redeem import hash_code

logger = logging.getLogger(__name__)


async def redeem(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    args = ctx.args or []
    if not args:
        await update.effective_message.reply_text(REDEEM_USAGE)
        return
    code = args[0].strip()
    # Never echo the code back into logs.
    logger.info("Redeem attempt uid=%s code_hash=%s", update.effective_user.id, hash_code(code)[:12])
    try:
        await ensure_user(update, svc)
        result = await svc.redeem.redeem(update.effective_user.id, code)
    except Exception:  # noqa: BLE001
        logger.exception("redeem failed")
        await update.effective_message.reply_text(REDEEM_INVALID)
        return

    if result.status == "ok":
        await update.effective_message.reply_text(
            REDEEM_OK.format(credit=fmt_usd(result.credit)), reply_markup=menu_kb()
        )
    elif result.status == "user_already_redeemed":
        await update.effective_message.reply_text(REDEEM_ALREADY)
    elif result.status == "already_used":
        await update.effective_message.reply_text(REDEEM_USED)
    else:
        await update.effective_message.reply_text(REDEEM_INVALID)

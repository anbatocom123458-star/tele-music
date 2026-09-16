"""Admin commands: /admin, /addcredit (ADMIN_TELEGRAM_ID only, spec §18)."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import is_admin, services
from app.bot.messages import (
    ADMIN_ADDCREDIT_OK,
    ADMIN_ADDCREDIT_USAGE,
    ADMIN_DENIED,
    ADMIN_NO_CONFIG,
    ADMIN_STATS,
    ADMIN_USER_NOT_FOUND,
    DB_DOWN,
)
from app.database.chroma import COLLECTION_REDEEM, COLLECTION_SVG_GEN, COLLECTION_USERS, COLLECTION_VOICE_GEN, get_rows

logger = logging.getLogger(__name__)


async def admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    if svc.cfg.admin_telegram_id is None:
        await update.effective_message.reply_text(ADMIN_NO_CONFIG)
        return
    if not is_admin(svc, update.effective_user.id):
        logger.warning("Non-admin uid=%s tried /admin", update.effective_user.id)
        await update.effective_message.reply_text(ADMIN_DENIED)
        return
    try:
        users_rows = await svc.db.run(lambda: svc.db.collection(COLLECTION_USERS).get())
        users = get_rows(users_rows)
        activated = sum(1 for u in users if u.get("redeemed"))
        total_credit = sum(float(u.get("credit") or 0.0) for u in users)
        remaining = await svc.redeem.remaining_count()
        voice_count = svc.db.collection(COLLECTION_VOICE_GEN).count()
        svg_count = svc.db.collection(COLLECTION_SVG_GEN).count()
    except Exception:  # noqa: BLE001
        logger.exception("admin stats failed")
        await update.effective_message.reply_text(DB_DOWN)
        return
    await update.effective_message.reply_text(
        ADMIN_STATS.format(
            users=len(users), activated=activated, credit=f"${total_credit:,.2f}",
            remaining=remaining, voice_gens=voice_count, svg_gens=svg_count,
            jobs=svc.jobs.active_count(),
        )
    )


async def addcredit(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    if svc.cfg.admin_telegram_id is None:
        await update.effective_message.reply_text(ADMIN_NO_CONFIG)
        return
    if not is_admin(svc, update.effective_user.id):
        logger.warning("Non-admin uid=%s tried /addcredit", update.effective_user.id)
        await update.effective_message.reply_text(ADMIN_DENIED)
        return
    args = ctx.args or []
    if len(args) != 2:
        await update.effective_message.reply_text(ADMIN_ADDCREDIT_USAGE)
        return
    try:
        target_uid = int(args[0])
        amount = round(float(args[1]), 2)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await update.effective_message.reply_text(ADMIN_ADDCREDIT_USAGE)
        return
    try:
        user = await svc.users.get(target_uid)
        if not user:
            await update.effective_message.reply_text(ADMIN_USER_NOT_FOUND)
            return
        new_balance = await svc.users.add_credit(target_uid, amount)
    except Exception:  # noqa: BLE001
        logger.exception("addcredit failed")
        await update.effective_message.reply_text(DB_DOWN)
        return
    await svc.usage.log(target_uid, "", "admin_credit", amount, detail="addcredit")
    await update.effective_message.reply_text(
        ADMIN_ADDCREDIT_OK.format(uid=target_uid, amount=amount, balance=f"${new_balance:,.2f}")
    )

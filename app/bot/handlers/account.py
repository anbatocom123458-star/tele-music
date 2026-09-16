"""/acc — account info + avatar (if Telegram provides one)."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import ensure_user, fmt_dt, fmt_usd, require_activated, services
from app.bot.messages import ACC_TEXT, GENERIC_DOWN
from app.bot.messages import display_name

logger = logging.getLogger(__name__)


async def acc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    try:
        user = await ensure_user(update, svc)
    except Exception:  # noqa: BLE001
        logger.exception("acc: db error")
        await update.effective_message.reply_text(GENERIC_DOWN)
        return
    if not await require_activated(update, user):
        return

    text = ACC_TEXT.format(
        name=display_name(user),
        uid=user["uid"],
        credit=fmt_usd(float(user.get("credit") or 0.0)),
        usage=user.get("usage_count") or 0,
        account_id=user.get("account_id") or "—",
        created=fmt_dt(float(user.get("created_at") or 0.0)),
    )

    avatar_sent = False
    try:
        photos = await ctx.bot.get_user_profile_photos(update.effective_user.id, limit=1)
        if photos.total_count > 0 and photos.photos[0]:
            file = await photos.photos[0][0].get_file()
            await update.effective_message.reply_photo(
                photo=file.file_id, caption=text
            )
            avatar_sent = True
    except Exception:  # noqa: BLE001
        logger.debug("avatar fetch failed", exc_info=True)
    if not avatar_sent:
        await update.effective_message.reply_text(text)

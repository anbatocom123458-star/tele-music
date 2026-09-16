"""/history — recent conversations with inline drill-down (spec §16)."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.common import ensure_user, fmt_cost, fmt_dt, require_activated, services
from app.bot.keyboards import history_kb
from app.bot.messages import BACK_TEXT, CONV_DETAIL, GENERIC_DOWN, HISTORY_EMPTY, HISTORY_TITLE

logger = logging.getLogger(__name__)


async def history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    svc = services(ctx)
    user = await ensure_user(update, svc)
    if not await require_activated(update, user):
        return
    try:
        convs = await svc.conversations.list_for_user(update.effective_user.id, limit=10)
    except Exception:  # noqa: BLE001
        logger.exception("history failed")
        await update.effective_message.reply_text(GENERIC_DOWN)
        return
    if not convs:
        await update.effective_message.reply_text(HISTORY_EMPTY)
        return
    await update.effective_message.reply_text(HISTORY_TITLE, reply_markup=history_kb(convs))


async def handle_conv_callback_entry(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    data = update.callback_query.data or ""
    await handle_conv_callback(update, ctx, data.split(":", 1)[-1])


async def handle_conv_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE, action: str) -> None:
    """conv:view:<cid> | conv:refresh"""
    query = update.callback_query
    svc = services(ctx)
    uid = update.effective_user.id
    await query.answer()

    if action == "refresh":
        convs = await svc.conversations.list_for_user(uid, limit=10)
        if not convs:
            await query.edit_message_text(HISTORY_EMPTY)
        else:
            try:
                await query.edit_message_reply_markup(reply_markup=history_kb(convs))
            except Exception:  # noqa: BLE001
                await query.message.reply_text(HISTORY_TITLE, reply_markup=history_kb(convs))
        return

    cid = action.split(":", 1)[-1]
    conv = await svc.conversations.get(cid)
    if not conv or conv.get("uid") != str(uid):
        await query.message.reply_text("Không tìm thấy conversation này (hoặc không thuộc tài khoản của bạn).")
        return

    extra = ""
    try:
        msgs = await svc.messages.list_for_conversation(cid, limit=10)
        lines = [f"• [{m.get('role')}/{m.get('content_type')}] {str(m.get('content') or '')[:80]}" for m in msgs]
        extra = "\n".join(lines) if lines else "Không có message nào."
    except Exception:  # noqa: BLE001
        logger.exception("loading conversation messages failed")

    detail = CONV_DETAIL.format(
        cid=conv.get("conversation_id"),
        uid=conv.get("uid"),
        created=fmt_dt(float(conv.get("created_at") or 0.0)),
        updated=fmt_dt(float(conv.get("updated_at") or 0.0)),
        workflow=str(conv.get("workflow") or "—").upper(),
        messages=conv.get("usage_count") or 0,
        cost=fmt_cost(float(conv.get("usage_cost") or 0.0)),
        extra=extra,
    )
    await query.message.reply_text(detail)

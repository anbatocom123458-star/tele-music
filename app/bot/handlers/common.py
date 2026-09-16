"""Shared handler helpers: user resolution, guards, formatting, errors."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.messages import DB_DOWN, NOT_ACTIVATED
from app.bot.state import Services
from app.database.users import PROCESSING_STATES

logger = logging.getLogger(__name__)

TZ_VIETNAM = timezone(timedelta(hours=7))


def services(ctx: ContextTypes.DEFAULT_TYPE) -> Services:
    return ctx.bot_data["services"]


def fmt_dt(ts: float) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(float(ts), TZ_VIETNAM).strftime("%d/%m/%Y %H:%M")


def fmt_usd(value: float) -> str:
    return f"${float(value):,.2f}"


def fmt_cost(value: float) -> str:
    value = round(float(value), 4)
    if value >= 1:
        return f"${value:,.2f}"
    text = f"${value:.4f}".rstrip("0")
    return text if not text.endswith(".") else text + "00"


async def ensure_user(update: Update, svc: Services) -> dict[str, Any]:
    tg_user = update.effective_user
    username = tg_user.username or ""
    first_name = tg_user.first_name or ""
    return await svc.users.ensure(tg_user.id, username=username, first_name=first_name)


async def require_activated(update: Update, user: dict[str, Any]) -> bool:
    if not user.get("redeemed"):
        await update.effective_message.reply_text(NOT_ACTIVATED)
        return False
    return True


def is_admin(svc: Services, uid: int) -> bool:
    return svc.cfg.admin_telegram_id is not None and int(uid) == svc.cfg.admin_telegram_id


async def notify_db_error(update: Update) -> None:
    await update.effective_message.reply_text(DB_DOWN)


async def send_friendly_error(update_or_query, message: str) -> None:
    if update_or_query is None:
        return
    try:
        if hasattr(update_or_query, "effective_message"):
            target = update_or_query.effective_message
        else:
            target = update_or_query
        if target is not None:
            await target.reply_text(message)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to send friendly error")


def state_is_processing(user: dict[str, Any]) -> bool:
    return user.get("state") in PROCESSING_STATES


def db_guard(svc: Services) -> bool:
    return all(
        svc.db.collections.get(name) is not None for name in ("users", "conversations")
    )

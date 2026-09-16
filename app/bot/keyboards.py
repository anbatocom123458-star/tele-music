"""Inline keyboards + per-user rate limiting."""
from __future__ import annotations

import time
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.config import Limits
from app.tts.voices import VOICES


def voice_selection_kb() -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for voice in VOICES.values():
        row.append(InlineKeyboardButton(voice.label, callback_data=f"voice:{voice.key}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Huỷ", callback_data="cancel:voice")])
    return InlineKeyboardMarkup(rows)


def svg_result_kb(gen_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🖼 Xem Preview", callback_data=f"svgaction:preview:{gen_id}"),
                InlineKeyboardButton("</> Xem Code", callback_data=f"svgaction:code:{gen_id}"),
            ],
            [
                InlineKeyboardButton("⬇️ Download SVG", callback_data=f"svgaction:download:{gen_id}"),
                InlineKeyboardButton("✖ Đóng", callback_data="cancel:svg_result"),
            ],
        ]
    )


def history_kb(conversations: list[dict[str, Any]]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"[{c['conversation_id']}] {str(c.get('workflow') or '?').upper()}",
                callback_data=f"conv:view:{c['conversation_id']}",
            )
        ]
        for c in conversations
    ]
    rows.append([InlineKeyboardButton("🔄 Làm mới", callback_data="conv:refresh")])
    return InlineKeyboardMarkup(rows)


def menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🎙 Voice", callback_data="menu:voice"),
             InlineKeyboardButton("🎨 SVG", callback_data="menu:svg")],
            [InlineKeyboardButton("🆕 New Chat", callback_data="menu:new"),
             InlineKeyboardButton("👤 Account", callback_data="menu:acc")],
            [InlineKeyboardButton("📚 History", callback_data="menu:history")],
        ]
    )


class RateLimiter:
    """Per-(uid, action) cooldown — in-memory, best-effort anti-spam."""

    def __init__(self, limits: Limits):
        self.cooldown = limits.command_cooldown_seconds
        self._last: dict[tuple[int, str], float] = {}

    def allow(self, uid: int | str, action: str) -> bool:
        uid = int(uid) if isinstance(uid, str) and uid.isdigit() else uid
        key = (uid, action)
        now = time.monotonic()
        last = self._last.get(key, 0.0)
        if now - last < self.cooldown:
            return False
        self._last[key] = now
        # opportunistic cleanup
        if len(self._last) > 5000:
            cutoff = now - 60
            self._last = {k: v for k, v in self._last.items() if v > cutoff}
        return True

"""Shared context object passed to every handler via bot_data."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.bot.keyboards import RateLimiter

if TYPE_CHECKING:
    from app.ai.client import AIClient
    from app.config import Config
    from app.database.chroma import Database
    from app.database.conversations import ConversationStore, MessageStore
    from app.database.redeem import RedeemStore
    from app.database.usage import (
        SvgGenerationStore,
        UsageStore,
        VoiceGenerationStore,
    )
    from app.database.users import UserStore
    from app.tts.engine import TTSEngine
    from app.workers.queue import JobManager


@dataclass
class Services:
    cfg: "Config"
    db: "Database"
    users: "UserStore"
    redeem: "RedeemStore"
    conversations: "ConversationStore"
    messages: "MessageStore"
    usage: "UsageStore"
    voice_gens: "VoiceGenerationStore"
    svg_gens: "SvgGenerationStore"
    tts: "TTSEngine"
    ai: "AIClient"
    jobs: "JobManager"
    limiter: RateLimiter = field(default_factory=RateLimiter)

    def as_dict(self) -> dict[str, Any]:
        return {"services": self}


def get_services(bot_data: dict) -> "Services":
    return bot_data["services"]

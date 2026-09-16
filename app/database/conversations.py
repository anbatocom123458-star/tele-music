"""Conversations and per-message records."""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.database.chroma import (
    COLLECTION_CONVERSATIONS,
    COLLECTION_MESSAGES,
    Database,
    ZERO_EMBEDDING,
    get_rows,
)


def new_conversation_id() -> str:
    return f"CHAT-{uuid.uuid4().hex[:8].upper()}"


class ConversationStore:
    def __init__(self, db: Database):
        self.db = db

    def _col(self):
        return self.db.collection(COLLECTION_CONVERSATIONS)

    async def create(self, uid: int | str, workflow: str = "") -> dict[str, Any]:
        cid = new_conversation_id()
        # extremely unlikely collision, retry once
        rows = await self.db.run(self._col().get, ids=[cid])
        if get_rows(rows):
            cid = new_conversation_id()
        meta = {
            "conversation_id": cid,
            "uid": str(uid),
            "created_at": time.time(),
            "updated_at": time.time(),
            "workflow": workflow,
            "usage_cost": 0.0,
            "usage_count": 0,
            "status": "active",
        }
        await self.db.run(
            self._col().add, ids=[cid], metadatas=[meta], embeddings=[ZERO_EMBEDDING]
        )
        return meta

    async def get(self, cid: str) -> dict[str, Any] | None:
        rows = await self.db.run(self._col().get, ids=[cid])
        found = get_rows(rows)
        return found[0] if found else None

    async def owns(self, cid: str, uid: int | str) -> bool:
        conv = await self.get(cid)
        return bool(conv and conv.get("uid") == str(uid))

    async def list_for_user(self, uid: int | str, limit: int = 10) -> list[dict[str, Any]]:
        rows = await self.db.run(
            lambda: self._col().get(where={"uid": str(uid)})
        )
        convs = get_rows(rows)
        convs.sort(key=lambda c: float(c.get("updated_at") or 0.0), reverse=True)
        return convs[:limit]

    async def touch(
        self, cid: str, workflow: str | None = None, add_cost: float = 0.0
    ) -> None:
        conv = await self.get(cid)
        if not conv:
            return
        conv.pop("id", None)
        conv["updated_at"] = time.time()
        if workflow:
            conv["workflow"] = workflow
        if add_cost:
            conv["usage_cost"] = round(float(conv.get("usage_cost") or 0.0) + float(add_cost), 4)
            conv["usage_count"] = int(conv.get("usage_count") or 0) + 1
        await self.db.run(self._col().update, ids=[cid], metadatas=[conv])


class MessageStore:
    def __init__(self, db: Database):
        self.db = db

    def _col(self):
        return self.db.collection(COLLECTION_MESSAGES)

    async def add(
        self,
        conversation_id: str,
        uid: int | str,
        role: str,
        content_type: str,
        content: str,
    ) -> str:
        msg_id = uuid.uuid4().hex
        meta = {
            "conversation_id": conversation_id,
            "uid": str(uid),
            "role": role,
            "content_type": content_type,
            "content": content[:4000],
            "created_at": time.time(),
        }
        await self.db.run(
            self._col().add, ids=[msg_id], metadatas=[meta], embeddings=[ZERO_EMBEDDING]
        )
        return msg_id

    async def list_for_conversation(
        self, conversation_id: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        rows = await self.db.run(
            lambda: self._col().get(where={"conversation_id": conversation_id})
        )
        msgs = get_rows(rows)
        msgs.sort(key=lambda m: float(m.get("created_at") or 0.0))
        return msgs[:limit]

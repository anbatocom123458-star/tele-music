"""Usage logs and generation records (metadata + references only).

Binary audio/images are never stored in ChromaDB; we keep Telegram file_ids
and short text (e.g. SVG source) as references.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.database.chroma import (
    COLLECTION_SVG_GEN,
    COLLECTION_USAGE,
    COLLECTION_VOICE_GEN,
    Database,
    ZERO_EMBEDDING,
    get_rows,
)


class UsageStore:
    def __init__(self, db: Database):
        self.db = db

    def _col(self):
        return self.db.collection(COLLECTION_USAGE)

    async def log(
        self,
        uid: int | str,
        conversation_id: str,
        kind: str,
        cost: float,
        detail: str = "",
    ) -> str:
        log_id = uuid.uuid4().hex
        meta = {
            "uid": str(uid),
            "conversation_id": conversation_id,
            "kind": kind,
            "cost": round(float(cost), 4),
            "detail": detail[:2000],
            "created_at": time.time(),
        }
        await self.db.run(
            self._col().add, ids=[log_id], metadatas=[meta], embeddings=[ZERO_EMBEDDING]
        )
        return log_id

    async def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = await self.db.run(lambda: self._col().get(limit=limit))
        logs = get_rows(rows)
        logs.sort(key=lambda l: float(l.get("created_at") or 0.0), reverse=True)
        return logs


class VoiceGenerationStore:
    def __init__(self, db: Database):
        self.db = db

    def _col(self):
        return self.db.collection(COLLECTION_VOICE_GEN)

    async def add(
        self,
        uid: int | str,
        conversation_id: str,
        voice_key: str,
        voice_label: str,
        text: str,
        chars: int,
        duration_s: float,
        cost: float,
        file_id: str = "",
        status: str = "ok",
    ) -> str:
        gen_id = uuid.uuid4().hex
        meta = {
            "uid": str(uid),
            "conversation_id": conversation_id,
            "voice_key": voice_key,
            "voice_label": voice_label,
            "text": text[:2000],
            "chars": chars,
            "duration_s": round(float(duration_s), 2),
            "cost": round(float(cost), 4),
            "file_id": file_id,
            "status": status,
            "created_at": time.time(),
        }
        await self.db.run(
            self._col().add, ids=[gen_id], metadatas=[meta], embeddings=[ZERO_EMBEDDING]
        )
        return gen_id

    async def get(self, gen_id: str) -> dict[str, Any] | None:
        rows = await self.db.run(self._col().get, ids=[gen_id])
        found = get_rows(rows)
        return found[0] if found else None


class SvgGenerationStore:
    def __init__(self, db: Database):
        self.db = db

    def _col(self):
        return self.db.collection(COLLECTION_SVG_GEN)

    async def add(
        self,
        uid: int | str,
        conversation_id: str,
        prompt: str,
        svg_source: str,
        width: int,
        height: int,
        element_count: int,
        cost: float,
        preview_file_id: str = "",
        code_file_id: str = "",
        status: str = "ok",
    ) -> str:
        gen_id = uuid.uuid4().hex
        meta = {
            "uid": str(uid),
            "conversation_id": conversation_id,
            "prompt": prompt[:2000],
            # SVG source is plain text -> safe to keep as a metadata reference.
            "svg_source": svg_source[:100_000],
            "width": int(width),
            "height": int(height),
            "element_count": int(element_count),
            "cost": round(float(cost), 4),
            "preview_file_id": preview_file_id,
            "code_file_id": code_file_id,
            "status": status,
            "created_at": time.time(),
        }
        await self.db.run(
            self._col().add, ids=[gen_id], metadatas=[meta], embeddings=[ZERO_EMBEDDING]
        )
        return gen_id

    async def get(self, gen_id: str) -> dict[str, Any] | None:
        rows = await self.db.run(self._col().get, ids=[gen_id])
        found = get_rows(rows)
        return found[0] if found else None

    async def update(self, gen_id: str, **fields: Any) -> None:
        row = await self.get(gen_id)
        if not row:
            return
        row.pop("id", None)
        row.update(fields)
        await self.db.run(self._col().update, ids=[gen_id], metadatas=[row])

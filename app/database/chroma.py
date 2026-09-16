"""ChromaDB HTTP client wrapper.

Every Chroma call is blocking (requests under the hood), so stores wrap them
with asyncio.to_thread via Database.run(). A fixed 8-dim zero embedding is
stored with each record: retrieval is done by id / metadata filters only,
so no embedding model is ever downloaded or executed client-side.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from app.config import ChromaConfig

logger = logging.getLogger(__name__)

COLLECTION_USERS = "users"
COLLECTION_REDEEM = "redeem_codes"
COLLECTION_CONVERSATIONS = "conversations"
COLLECTION_MESSAGES = "messages"
COLLECTION_USAGE = "usage_logs"
COLLECTION_VOICE_GEN = "voice_generations"
COLLECTION_SVG_GEN = "svg_generations"

ALL_COLLECTIONS = (
    COLLECTION_USERS,
    COLLECTION_REDEEM,
    COLLECTION_CONVERSATIONS,
    COLLECTION_MESSAGES,
    COLLECTION_USAGE,
    COLLECTION_VOICE_GEN,
    COLLECTION_SVG_GEN,
)

ZERO_EMBEDDING = [0.0] * 8


class Database:
    def __init__(self, cfg: ChromaConfig):
        self.cfg = cfg
        self._client: Any = None
        self.collections: dict[str, Any] = {}

    # -- lifecycle -----------------------------------------------------
    def connect_sync(self) -> None:
        """Blocking connect + ensure all collections exist. Call once at boot."""
        import chromadb  # imported lazily; heavy dependency

        headers: dict[str, str] = {}
        if self.cfg.apikey:
            headers["Authorization"] = f"Bearer {self.cfg.apikey}"
        if self.cfg.secret:
            headers["X-Chroma-Token"] = self.cfg.secret
        logger.info("Connecting ChromaDB at %s:%s db=%s", self.cfg.host, self.cfg.port, self.cfg.database)
        self._client = chromadb.HttpClient(
            host=self.cfg.host,
            port=self.cfg.port,
            ssl=self.cfg.ssl,
            headers=headers or None,
            tenant=self.cfg.tenant,
            database=self.cfg.database,
        )
        heartbeat = self._client.heartbeat()
        logger.info("ChromaDB heartbeat ok: %s", heartbeat)
        for name in ALL_COLLECTIONS:
            self.collections[name] = self._client.get_or_create_collection(name=name)
        logger.info("ChromaDB collections ready: %s", ", ".join(ALL_COLLECTIONS))

    async def connect(self) -> None:
        await asyncio.to_thread(self.connect_sync)

    def collection(self, name: str) -> Any:
        if name not in self.collections:
            raise RuntimeError(f"Collection {name} chưa được khởi tạo.")
        return self.collections[name]

    async def run(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Run a blocking Chroma operation in a worker thread."""
        return await asyncio.to_thread(fn, *args, **kwargs)

    async def ping(self, timeout: float = 3.0) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._client.heartbeat), timeout=timeout
            ) is not None
        except Exception as exc:
            logger.warning("ChromaDB ping failed: %s", exc)
            return False


def get_rows(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalize a chroma get() result into a list of {id, ...metadata}."""
    ids = result.get("ids") or []
    metas = result.get("metadatas") or []
    # chroma may return nested lists when multiple query sets are present
    if ids and isinstance(ids[0], list):
        ids = [i for sub in ids for i in sub]
        metas = [m for sub in (metas or []) for m in sub]
    rows: list[dict[str, Any]] = []
    for i, meta in zip(ids, metas):
        row = dict(meta or {})
        row["id"] = i
        rows.append(row)
    return rows

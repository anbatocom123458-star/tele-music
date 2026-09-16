"""Redeem system.

ENV codes are the *initial seed only*. After seeding:
- DB stores the SHA-256 hash of each code (never plaintext).
- Usage state (used/unused, used_by, used_at) lives in the database, so a
  Railway restart or a second replica cannot re-enable a spent code.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Any

from app.database.chroma import (
    COLLECTION_REDEEM,
    Database,
    ZERO_EMBEDDING,
    get_rows,
)
from app.database.users import UserStore


@dataclass
class RedeemResult:
    status: str  # "ok" | "invalid" | "already_used" | "user_already_redeemed"
    credit: float = 0.0
    account_id: str = ""
    label: str = ""


def hash_code(code: str) -> str:
    normalized = code.strip().upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class RedeemStore:
    def __init__(self, db: Database, users: UserStore, initial_credit: float):
        self.db = db
        self.users = users
        self.initial_credit = initial_credit

    def _col(self):
        return self.db.collection(COLLECTION_REDEEM)

    # -- seeding ---------------------------------------------------------
    async def seed(self, codes: dict[str, str]) -> int:
        """Insert ENV codes (hashed) that are not present yet. Idempotent."""
        created = 0
        for label, code in codes.items():
            code_hash = hash_code(code)
            rows = await self.db.run(self._col().get, ids=[code_hash])
            if get_rows(rows):
                continue
            meta = {
                "label": label,
                "credit": self.initial_credit,
                "used": False,
                "used_by": "",
                "used_at": 0.0,
                "created_at": time.time(),
            }
            await self.db.run(
                self._col().add,
                ids=[code_hash],
                metadatas=[meta],
                embeddings=[ZERO_EMBEDDING],
            )
            created += 1
        return created

    async def remaining_count(self) -> int:
        rows = await self.db.run(lambda: self._col().get(where={"used": False}))
        return len(get_rows(rows))

    # -- redemption ------------------------------------------------------
    async def redeem(self, uid: int | str, code: str) -> RedeemResult:
        uid = str(uid)
        code_hash = hash_code(code)

        user = await self.users.get(uid)
        if user and user.get("redeemed"):
            return RedeemResult(status="user_already_redeemed")

        rows = await self.db.run(self._col().get, ids=[code_hash])
        found = get_rows(rows)
        if not found:
            return RedeemResult(status="invalid")
        code_meta = found[0]
        if code_meta.get("used"):
            return RedeemResult(status="already_used")

        # Activate account
        user = await self.users.ensure(uid)
        account_id = f"ACC-{uuid.uuid4().hex[:8].upper()}"
        await self.users.set_fields(
            uid,
            redeemed=True,
            activated_at=time.time(),
            credit=float(code_meta.get("credit") or self.initial_credit),
            usage_count=0,
            account_id=account_id,
            redeem_code_hash=code_hash,
            state="IDLE",
            pending_text="",
            pending_voice="",
        )

        # Mark code as spent
        code_meta.pop("id", None)
        code_meta.update(
            {
                "used": True,
                "used_by": uid,
                "used_at": time.time(),
            }
        )
        await self.db.run(
            self._col().update, ids=[code_hash], metadatas=[code_meta]
        )
        return RedeemResult(
            status="ok",
            credit=float(code_meta.get("credit") or self.initial_credit),
            account_id=account_id,
            label=str(code_meta.get("label") or ""),
        )

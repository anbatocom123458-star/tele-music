"""User accounts. Credit / usage / state live here — server-side only."""
from __future__ import annotations

import time
import uuid
from typing import Any

from app.database.chroma import COLLECTION_USERS, Database, ZERO_EMBEDDING, get_rows

# User states (state machine, spec §20)
STATE_IDLE = "IDLE"
STATE_VOICE_WAITING_TEXT = "VOICE_WAITING_TEXT"
STATE_VOICE_SELECTING_VOICE = "VOICE_SELECTING_VOICE"
STATE_VOICE_PROCESSING = "VOICE_PROCESSING"
STATE_SVG_WAITING_PROMPT = "SVG_WAITING_PROMPT"
STATE_SVG_PROCESSING = "SVG_PROCESSING"

PROCESSING_STATES = {STATE_VOICE_PROCESSING, STATE_SVG_PROCESSING}


def _now() -> float:
    return time.time()


class UserStore:
    def __init__(self, db: Database):
        self.db = db

    def _col(self):
        return self.db.collection(COLLECTION_USERS)

    # -- core CRUD -----------------------------------------------------
    async def get(self, uid: int | str) -> dict[str, Any] | None:
        rows = await self.db.run(self._col().get, ids=[str(uid)])
        found = get_rows(rows)
        return found[0] if found else None

    async def ensure(
        self, uid: int | str, username: str = "", first_name: str = ""
    ) -> dict[str, Any]:
        uid = str(uid)
        user = await self.get(uid)
        if user:
            patch: dict[str, Any] = {}
            if username and user.get("username") != username:
                patch["username"] = username
            if first_name and user.get("first_name") != first_name:
                patch["first_name"] = first_name
            if patch:
                await self.set_fields(uid, **patch)
                user.update(patch)
            return user
        meta = {
            "uid": uid,
            "username": username or "",
            "first_name": first_name or "",
            "credit": 0.0,
            "usage_count": 0,
            "redeemed": False,
            "state": STATE_IDLE,
            "active_conversation": "",
            "pending_text": "",
            "pending_voice": "",
            "account_id": "",
            "redeem_code_hash": "",
            "created_at": _now(),
            "activated_at": 0.0,
        }
        await self.db.run(
            self._col().add, ids=[uid], metadatas=[meta], embeddings=[ZERO_EMBEDDING]
        )
        return meta

    async def set_fields(self, uid: int | str, **fields: Any) -> None:
        uid = str(uid)
        current = await self.get(uid)
        if not current:
            raise RuntimeError(f"User {uid} không tồn tại.")
        current.pop("id", None)
        current.update(fields)
        await self.db.run(self._col().update, ids=[uid], metadatas=[current])

    async def set_state(self, uid: int | str, state: str) -> None:
        await self.set_fields(uid, state=state)

    # -- credit --------------------------------------------------------
    async def add_credit(self, uid: int | str, amount: float) -> float:
        user = await self.get(uid)
        if not user:
            raise RuntimeError(f"User {uid} không tồn tại.")
        new_balance = round(float(user.get("credit") or 0.0) + float(amount), 4)
        await self.set_fields(uid, credit=new_balance)
        return new_balance

    async def try_charge(self, uid: int | str, cost: float) -> tuple[bool, float]:
        """Charge cost if balance suffices. Returns (ok, new_balance_or_current)."""
        user = await self.get(uid)
        if not user:
            return False, 0.0
        balance = round(float(user.get("credit") or 0.0), 4)
        cost = round(float(cost), 4)
        if balance < cost:
            return False, balance
        new_balance = round(balance - cost, 4)
        await self.set_fields(uid, credit=new_balance, usage_count=int(user.get("usage_count") or 0) + 1)
        return True, new_balance

    async def increment_usage(self, uid: int | str) -> int:
        user = await self.get(uid)
        if not user:
            return 0
        count = int(user.get("usage_count") or 0) + 1
        await self.set_fields(uid, usage_count=count)
        return count

    # -- recovery (Railway restart) ------------------------------------
    async def reset_processing_states(self) -> int:
        rows = await self.db.run(
            lambda: self._col().get(where={"state": STATE_VOICE_PROCESSING})
        )
        rows2 = await self.db.run(
            lambda: self._col().get(where={"state": STATE_SVG_PROCESSING})
        )
        users = get_rows(rows) + get_rows(rows2)
        for user in users:
            uid = user["id"]
            await self.set_fields(
                uid,
                state=STATE_IDLE,
                pending_text="",
                pending_voice="",
            )
        return len(users)

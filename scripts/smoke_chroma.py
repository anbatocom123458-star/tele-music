"""Integration smoke test against a REAL ChromaDB HTTP server.

Prereq: chroma run --path /tmp/chroma_e2e --port 8100
Run:   .venv312/bin/python scripts/smoke_chroma.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import ChromaConfig  # noqa: E402
from app.database.chroma import Database  # noqa: E402
from app.database.conversations import ConversationStore, MessageStore  # noqa: E402
from app.database.redeem import RedeemStore  # noqa: E402
from app.database.users import STATE_VOICE_PROCESSING, UserStore  # noqa: E402
from app.database.usage import SvgGenerationStore, UsageStore, VoiceGenerationStore  # noqa: E402


async def main() -> None:
    db = Database(ChromaConfig("localhost", 8100, False, "default_database", "default_tenant", "", ""))
    await db.connect()
    assert await db.ping()

    users = UserStore(db)
    redeem = RedeemStore(db, users, initial_credit=100.0)
    conversations = ConversationStore(db)
    messages = MessageStore(db)
    usage = UsageStore(db)
    voice_gens = VoiceGenerationStore(db)
    svg_gens = SvgGenerationStore(db)

    # Clean slate for the fixed test UID / codes (restart-persistence makes
    # re-runs see previous state — itself the behavior the spec requires).
    from app.database.chroma import ALL_COLLECTIONS

    for name in ALL_COLLECTIONS:
        col = db.collection(name)
        rows = await db.run(lambda c=col: c.get())
        ids = rows.get("ids") or []
        if ids:
            await db.run(lambda c=col, i=ids: c.delete(ids=i))


    # seed + redeem
    created = await redeem.seed({"RC1": "TESTCODE1", "RC2": "TESTCODE2"})
    assert created in (0, 2)  # 2 on a fresh DB, 0 when re-run (idempotent seeding)
    assert await redeem.seed({"RC1": "TESTCODE1"}) == 0  # idempotent

    result = await redeem.redeem(100200300, "testcode1")
    assert result.status == "ok" and result.credit == 100.0, result
    user = await users.get(100200300)
    assert user["redeemed"] and user["account_id"].startswith("ACC-")
    assert (await redeem.redeem(999, "testcode1")).status == "already_used"
    assert (await redeem.redeem(100200300, "testcode2")).status == "user_already_redeemed"

    # credit flow
    ok, bal = await users.try_charge(100200300, 0.05)
    assert ok and abs(bal - 99.95) < 1e-9
    ok, bal = await users.try_charge(100200300, 999.0)
    assert not ok

    # conversation + messages
    conv = await conversations.create(100200300, workflow="voice")
    cid = conv["conversation_id"]
    assert cid.startswith("CHAT-")
    await messages.add(cid, 100200300, "user", "voice_text", "Xin chào")
    await conversations.touch(cid, workflow="voice", add_cost=0.05)
    got = await conversations.get(cid)
    assert got["usage_cost"] == 0.05
    assert await conversations.owns(cid, 100200300) is True
    assert await conversations.owns(cid, 424242) is False  # isolation

    # records
    await voice_gens.add(100200300, cid, "NU_1", "👩 Nữ 1", "Xin chào", 8, 2.5, 0.05, file_id="FID123")
    gen = await svg_gens.add(100200300, cid, "một ngôi nhà", "<svg>..</svg>", 1024, 1024, 12, 0.1)
    await usage.log(100200300, cid, "voice", 0.05, detail="NU_1")
    await usage.log(100200300, cid, "svg", 0.10, detail="1024x1024")
    logs = await usage.recent(limit=5)
    assert any(l["kind"] in ("voice", "svg") for l in logs), logs
    rec = await svg_gens.get(gen)
    assert rec["svg_source"] == "<svg>..</svg>"
    await svg_gens.update(gen, preview_file_id="PFID")
    assert (await svg_gens.get(gen))["preview_file_id"] == "PFID"

    # history listing
    convs = await conversations.list_for_user(100200300)
    assert any(c["conversation_id"] == cid for c in convs)

    # restart recovery
    await users.set_state(100200300, STATE_VOICE_PROCESSING)
    reset = await users.reset_processing_states()
    assert reset == 1
    assert (await users.get(100200300))["state"] == "IDLE"

    print(f"CHROMA_E2E_OK (conversations={len(convs)}, logs={len(logs)})")


if __name__ == "__main__":
    asyncio.run(main())

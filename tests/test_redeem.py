"""Redeem flow: valid / invalid / duplicate code / duplicate user (spec §4)."""
from __future__ import annotations

import pytest

from app.database.chroma import Database
from app.database.redeem import RedeemStore, hash_code
from app.database.users import UserStore
from tests.fake_chroma import FakeCollection


@pytest.fixture
def db() -> Database:
    database = Database.__new__(Database)
    database.collections = {
        "users": FakeCollection(),
        "redeem_codes": FakeCollection(),
        "conversations": FakeCollection(),
        "messages": FakeCollection(),
        "usage_logs": FakeCollection(),
        "voice_generations": FakeCollection(),
        "svg_generations": FakeCollection(),
    }
    return database


@pytest.fixture
def stores(db):
    users = UserStore(db)
    redeem = RedeemStore(db, users, initial_credit=100.0)
    return users, redeem


@pytest.mark.asyncio
async def test_seed_hashes_codes(db, stores):
    _, redeem = stores
    created = await redeem.seed({"RC1": "CODE-1", "RC2": "CODE-2"})
    assert created == 2
    col = db.collections["redeem_codes"]
    assert hash_code("CODE-1") in col.data
    # plaintext never stored
    for meta in col.data.values():
        assert "CODE-1" not in str(meta)
    # idempotent
    assert await redeem.seed({"RC1": "CODE-1"}) == 0


@pytest.mark.asyncio
async def test_redeem_valid_then_invalid_reuse(db, stores):
    users, redeem = stores
    await redeem.seed({"RC1": "MYCODE123"})
    ok = await redeem.redeem(111, "mycode123")  # case-insensitive normalization
    assert ok.status == "ok" and ok.credit == 100.0
    user = await users.get(111)
    assert user["redeemed"] is True and user["credit"] == 100.0
    assert user["account_id"].startswith("ACC-")
    # code is now spent in DB
    assert db.collections["redeem_codes"].data[hash_code("MYCODE123")]["used"] is True
    # reuse by anyone -> already_used
    again_same_user = await redeem.redeem(111, "MYCODE123")
    assert again_same_user.status == "user_already_redeemed"
    again_other_user = await redeem.redeem(222, "MYCODE123")
    assert again_other_user.status == "already_used"


@pytest.mark.asyncio
async def test_redeem_invalid_code(db, stores):
    _, redeem = stores
    await redeem.seed({"RC1": "GOOD"})
    assert (await redeem.redeem(1, "WRONG")).status == "invalid"
    assert (await redeem.redeem(1, "")).status == "invalid"


@pytest.mark.asyncio
async def test_user_without_prior_redeem_can_use_fresh_code(db, stores):
    users, redeem = stores
    await redeem.seed({"RC1": "A", "RC2": "B"})
    assert (await redeem.redeem(5, "A")).status == "ok"
    assert (await redeem.redeem(5, "B")).status == "user_already_redeemed"
    # second user CAN still redeem an unused code
    assert (await redeem.redeem(6, "B")).status == "ok"

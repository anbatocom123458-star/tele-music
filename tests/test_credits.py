"""Billing cost abstraction + user credit deduction (fake collection)."""
from __future__ import annotations

import pytest

from app.billing.credits import (
    VOICE_MIN_COST,
    calculate_svg_cost,
    calculate_voice_cost,
    format_cost,
)
from app.database.chroma import Database
from app.database.users import UserStore
from tests.fake_chroma import FakeCollection


@pytest.fixture
def db() -> Database:
    database = Database.__new__(Database)  # skip chroma connect
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


@pytest.mark.asyncio
async def test_voice_cost_scales_with_chars():
    short = calculate_voice_cost("abc")
    assert short.amount == VOICE_MIN_COST
    long_ = calculate_voice_cost("a" * 2000)
    assert long_.amount == pytest.approx(0.1)
    assert long_.chars == 2000


@pytest.mark.asyncio
async def test_svg_cost_flat():
    assert calculate_svg_cost(0).amount == pytest.approx(0.10)
    assert calculate_svg_cost(100).amount > calculate_svg_cost(0).amount


@pytest.mark.asyncio
async def test_charge_deducts_and_counts_usage(db):
    users = UserStore(db)
    await users.ensure(42, username="tester")
    await users.add_credit(42, 10.0)
    ok, balance = await users.try_charge(42, 0.05)
    assert ok and balance == pytest.approx(9.95)
    user = await users.get(42)
    assert user["usage_count"] == 1


@pytest.mark.asyncio
async def test_charge_refuses_when_insufficient(db):
    users = UserStore(db)
    await users.ensure(7)
    ok, balance = await users.try_charge(7, 0.5)
    assert not ok
    assert balance == 0.0
    user = await users.get(7)
    assert user["usage_count"] == 0


@pytest.mark.asyncio
async def test_format_cost():
    assert format_cost(0.0500) == "$0.05"
    assert format_cost(1.5) == "$1.50"

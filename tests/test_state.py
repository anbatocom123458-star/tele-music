"""State machine persistence + restart recovery (spec §20)."""
from __future__ import annotations

import pytest

from app.database.chroma import Database
from app.database.users import (
    PROCESSING_STATES,
    STATE_IDLE,
    STATE_SVG_PROCESSING,
    STATE_VOICE_PROCESSING,
    STATE_VOICE_SELECTING_VOICE,
    STATE_VOICE_WAITING_TEXT,
    UserStore,
)
from tests.fake_chroma import FakeCollection


@pytest.fixture
def users() -> UserStore:
    database = Database.__new__(Database)
    database.collections = {"users": FakeCollection()}
    return UserStore(database)


@pytest.mark.asyncio
async def test_state_transitions_persist(users):
    await users.ensure(9, username="u9")
    for state in (STATE_VOICE_WAITING_TEXT, STATE_VOICE_SELECTING_VOICE, STATE_VOICE_PROCESSING):
        await users.set_state(9, state)
        current = await users.get(9)
        assert current["state"] == state


@pytest.mark.asyncio
async def test_restart_recovery_clears_processing(users):
    await users.ensure(1)
    await users.ensure(2)
    await users.ensure(3)
    await users.set_fields(1, state=STATE_VOICE_WAITING_TEXT, pending_text="hello")
    await users.set_fields(2, state=STATE_SVG_PROCESSING)
    await users.set_fields(3, state=STATE_VOICE_SELECTING_VOICE, pending_text="keepme")

    reset = await users.reset_processing_states()
    assert reset == 1
    assert (await users.get(1))["state"] == STATE_VOICE_WAITING_TEXT  # untouched
    assert (await users.get(2))["state"] == STATE_IDLE  # stale processing cleared
    assert (await users.get(3))["state"] == STATE_VOICE_SELECTING_VOICE  # untouched


@pytest.mark.asyncio
async def test_processing_states_set_contains_expected(users):
    assert STATE_SVG_PROCESSING in PROCESSING_STATES
    assert STATE_IDLE not in PROCESSING_STATES

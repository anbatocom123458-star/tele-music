"""Job queue: concurrency caps, per-user limit, timeout, error routing."""
from __future__ import annotations

import asyncio

import pytest

from app.config import Limits
from app.workers.queue import JobManager


async def _drain(jobs: JobManager) -> None:
    while jobs.active_count() > 0 or not jobs._queue.empty():
        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_per_user_limit():
    jobs = JobManager(Limits(max_jobs_per_user=1, max_global_jobs=4), worker_count=2)
    jobs.start()
    started = asyncio.Event()

    async def slow():
        started.set()
        await asyncio.sleep(0.2)
        return "done"

    ok = await jobs.submit(1, "t", slow)
    assert ok is True
    await started.wait()
    # same user is busy
    assert await jobs.submit(1, "t", slow) is False
    # another user is fine
    assert await jobs.submit(2, "t", slow) is True
    await _drain(jobs)
    await jobs.stop()


@pytest.mark.asyncio
async def test_success_and_error_callbacks():
    jobs = JobManager(Limits(max_jobs_per_user=1), worker_count=2)
    jobs.start()
    results, errors = [], []

    async def ok_job():
        return 42

    async def bad_job():
        raise ValueError("boom")

    await jobs.submit(1, "ok", ok_job, on_success=results.append)
    await jobs.submit(2, "bad", bad_job, on_error=errors.append)
    await _drain(jobs)
    assert results == [42]
    assert len(errors) == 1 and isinstance(errors[0], ValueError)
    # user is freed after finish
    assert not jobs.busy(1) and not jobs.busy(2)
    await jobs.stop()


@pytest.mark.asyncio
async def test_timeout_kills_job():
    jobs = JobManager(Limits(max_jobs_per_user=1), worker_count=1)
    jobs.start()
    errors = []

    async def never():
        await asyncio.sleep(10)

    await jobs.submit(1, "never", never, on_error=errors.append, timeout=1)
    await _drain(jobs)
    assert len(errors) == 1 and isinstance(errors[0], asyncio.TimeoutError)
    await jobs.stop()

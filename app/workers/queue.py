"""Simple async job queue.

- Handlers never run TTS/AI work inline, so Telegram polling never blocks.
- Global concurrency is capped (CPU-friendly), and each user can have at
  most N active jobs (anti-spam).
- Every job runs under a hard timeout; failures surface via on_error.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from app.config import Limits

logger = logging.getLogger(__name__)

SUCCESS_CB = Callable[[Any], Awaitable[None]]
ERROR_CB = Callable[[BaseException], Awaitable[None]]


class JobManager:
    def __init__(self, limits: Limits, worker_count: int | None = None):
        self.limits = limits
        self._queue: asyncio.Queue = asyncio.Queue()
        self._active: dict[int, int] = {}
        self._workers: list[asyncio.Task] = []
        self._count = worker_count or max(1, limits.max_global_jobs)
        self._stopping = False

    # -- lifecycle -------------------------------------------------------
    def start(self) -> None:
        for i in range(self._count):
            self._workers.append(
                asyncio.create_task(self._worker_loop(i), name=f"job-worker-{i}")
            )
        logger.info("Job queue started with %d workers", self._count)

    async def stop(self) -> None:
        self._stopping = True
        for _ in self._workers:
            await self._queue.put(None)  # poison pills
        await asyncio.gather(*self._workers, return_exceptions=True)

    # -- state -----------------------------------------------------------
    def busy(self, uid: int | str) -> bool:
        return self._active.get(uid, 0) >= self.limits.max_jobs_per_user

    def active_count(self) -> int:
        return sum(self._active.values())

    # -- submission -------------------------------------------------------
    async def submit(
        self,
        uid: int | str,
        name: str,
        coro_fn: Callable[[], Awaitable[Any]],
        on_success: SUCCESS_CB | None = None,
        on_error: ERROR_CB | None = None,
        timeout: int | None = None,
    ) -> bool:
        """Returns False (and does nothing) if the user already has a running job."""
        if self.busy(uid):
            return False
        self._active[uid] = self._active.get(uid, 0) + 1
        await self._queue.put(
            {
                "uid": uid,
                "name": name,
                "coro_fn": coro_fn,
                "on_success": on_success,
                "on_error": on_error,
                "timeout": timeout or self.limits.tts_timeout_seconds,
            }
        )
        logger.info("Job submitted uid=%s name=%s queue=%d", uid, name, self._queue.qsize())
        return True

    # -- worker -----------------------------------------------------------
    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            job = await self._queue.get()
            if job is None:  # poison pill
                self._queue.task_done()
                return
            uid = job["uid"]
            try:
                try:
                    result = await asyncio.wait_for(job["coro_fn"](), timeout=job["timeout"])
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    logger.error("Job %s (uid=%s) failed: %s", job["name"], uid, exc)
                    logger.debug("Job failure detail", exc_info=True)
                    if job["on_error"]:
                        await _safe_call(job["on_error"], exc)
                else:
                    if job["on_success"]:
                        await _safe_call(job["on_success"], result)
            finally:
                self._active[uid] = max(0, self._active.get(uid, 1) - 1)
                if self._active[uid] == 0:
                    self._active.pop(uid, None)
                self._queue.task_done()


async def _safe_call(cb: Callable[[Any], Awaitable[None]], arg: Any) -> None:
    try:
        await cb(arg)
    except Exception:  # noqa: BLE001 - callbacks must never kill the worker
        logger.error("Job callback failed", exc_info=True)

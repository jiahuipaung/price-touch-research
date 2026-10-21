from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

Sleep = Callable[[float], Awaitable[None]]


class ReplayClock:
    def __init__(self, sleep: Sleep = asyncio.sleep) -> None:
        self._sleep = sleep
        self._running = asyncio.Event()
        self._running.set()

    @classmethod
    def immediate(cls) -> "ReplayClock":
        async def no_sleep(_: float) -> None:
            return None

        return cls(no_sleep)

    def pause(self) -> None:
        self._running.clear()

    def resume(self) -> None:
        self._running.set()

    async def wait_until_running(self) -> None:
        await self._running.wait()

    async def wait_event_delta(self, event_seconds: float, speed: float) -> None:
        if speed <= 0:
            raise ValueError("replay speed must be positive")
        await self._sleep(max(0.0, event_seconds) / speed)

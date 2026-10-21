from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from price_touch.domain import MarketEvent
from price_touch.market.base import MarketAdapter


class AdapterUnavailable(RuntimeError):
    pass


class AdapterSupervisor:
    def __init__(
        self,
        factory: Callable[[], MarketAdapter],
        *,
        max_attempts: int = 5,
        base_backoff_seconds: float = 1,
        max_backoff_seconds: float = 30,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.factory = factory
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep = sleep
        self.terminal_error: Exception | None = None

    async def run(self) -> AsyncIterator[MarketEvent]:
        for attempt in range(self.max_attempts):
            try:
                async for event in self.factory().events():
                    yield event
                self.terminal_error = None
                return
            except Exception as error:
                if attempt == self.max_attempts - 1:
                    self.terminal_error = error
                    raise AdapterUnavailable(str(error)) from error
                backoff = min(self.base_backoff_seconds * (2**attempt), self.max_backoff_seconds)
                await self.sleep(backoff)

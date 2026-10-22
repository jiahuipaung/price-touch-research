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
        on_transport_change: Callable[[bool], None] | None = None,
        restart_on_completion: bool = False,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self.factory = factory
        self.max_attempts = max_attempts
        self.base_backoff_seconds = base_backoff_seconds
        self.max_backoff_seconds = max_backoff_seconds
        self.sleep = sleep
        self.on_transport_change = on_transport_change
        self.restart_on_completion = restart_on_completion
        self.terminal_error: Exception | None = None
        self._transport_state: bool | None = None

    def _report_transport(self, available: bool) -> None:
        if self._transport_state is available:
            return
        self._transport_state = available
        if self.on_transport_change is not None:
            self.on_transport_change(available)

    async def run(self) -> AsyncIterator[MarketEvent]:
        for attempt in range(self.max_attempts):
            try:
                async for event in self.factory().events():
                    self._report_transport(True)
                    yield event
                if self.restart_on_completion:
                    raise ConnectionError("market stream ended")
                self.terminal_error = None
                return
            except Exception as error:
                self._report_transport(False)
                if attempt == self.max_attempts - 1:
                    self.terminal_error = error
                    raise AdapterUnavailable(str(error)) from error
                backoff = min(self.base_backoff_seconds * (2**attempt), self.max_backoff_seconds)
                await self.sleep(backoff)

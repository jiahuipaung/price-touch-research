from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from price_touch.domain import MarketEvent
from price_touch.market.base import MarketAdapter
from price_touch.market.supervisor import AdapterSupervisor, AdapterUnavailable
from price_touch.service import ForecastService

Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]
AdapterFactory = Callable[[], MarketAdapter]
WarmupLoader = Callable[[], Awaitable[list[MarketEvent]]]


class LiveRuntime:
    """Consume live events continuously while publishing a complete matrix on a fixed cadence."""

    def __init__(
        self,
        service: ForecastService,
        *,
        adapter_factory: AdapterFactory,
        warmup_loader: WarmupLoader | None = None,
        clock: Clock | None = None,
        sleep: Sleep = asyncio.sleep,
        reconnect_attempts: int = 5,
    ) -> None:
        self.service = service
        self.adapter_factory = adapter_factory
        self.warmup_loader = warmup_loader
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleep = sleep
        self.reconnect_attempts = reconnect_attempts
        self._first_event = asyncio.Event()

    def _set_transport(self, available: bool) -> None:
        self.service.transport_ok = available

    async def _ingest(self) -> None:
        supervisor = AdapterSupervisor(
            self.adapter_factory,
            max_attempts=self.reconnect_attempts,
            on_transport_change=self._set_transport,
            restart_on_completion=True,
        )
        try:
            async for event in supervisor.run():
                if self.service.ingest(event):
                    self._first_event.set()
        except AdapterUnavailable:
            self.service.transport_ok = False

    async def _warmup(self) -> None:
        if self.warmup_loader is None:
            return
        try:
            events = await self.warmup_loader()
        except Exception:
            return
        for event in events:
            self.service.ingest(event)

    async def run(self) -> None:
        await self._warmup()
        ingest_task = asyncio.create_task(self._ingest())
        try:
            await self._first_event.wait()
            while True:
                now = self.clock()
                await self.service.publish(now)
                self.service.mature(now)
                await self.sleep(self.service.settings.publication_interval_seconds)
        finally:
            ingest_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await ingest_task

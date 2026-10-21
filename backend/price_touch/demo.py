from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from price_touch.domain import EventKind, MarketEvent
from price_touch.service import ForecastService


class DemoRuntime:
    """Credential-free deterministic stream used only by the offline acceptance mode."""

    def __init__(
        self,
        service: ForecastService,
        *,
        fault_step: int = 2,
        fault_period: int = 8,
    ) -> None:
        self.service = service
        self.fault_step = fault_step
        self.fault_period = fault_period
        self.step_count = 0

    async def step(self, now: datetime) -> None:
        pattern = (0, 120, -80, 260, -160, 900, -320, 40)
        offset = pattern[self.step_count % len(pattern)]
        event = MarketEvent(
            asset="BTC",
            instrument="BTCUSDT",
            event_time=now,
            received_time=now,
            price_ticks=10_000_000 + offset,
            trade_id=f"offline-{self.step_count}",
            kind=EventKind.TRADE,
        )
        self.service.ingest(event)
        self.service.transport_ok = self.step_count % self.fault_period != self.fault_step
        await self.service.publish(now)
        self.service.mature(now)
        self.step_count += 1

    async def run(self) -> None:
        while True:
            await self.step(datetime.now(UTC))
            await asyncio.sleep(self.service.settings.publication_interval_seconds)

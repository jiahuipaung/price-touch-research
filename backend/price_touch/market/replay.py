from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from price_touch.domain import MarketEvent
from price_touch.market.clock import ReplayClock


class ReplayAdapter:
    def __init__(
        self,
        events: Sequence[MarketEvent],
        *,
        speed: float = 1.0,
        seed: int = 0,
        clock: ReplayClock | None = None,
    ) -> None:
        if speed <= 0:
            raise ValueError("replay speed must be positive")
        self._events = sorted(events, key=lambda event: (event.event_time, event.trade_id))
        self.speed = speed
        self.seed = seed
        self.clock = clock or ReplayClock()

    def pause(self) -> None:
        self.clock.pause()

    def resume(self) -> None:
        self.clock.resume()

    async def events(self) -> AsyncIterator[MarketEvent]:
        previous: MarketEvent | None = None
        for event in self._events:
            await self.clock.wait_until_running()
            if previous is not None:
                delta = (event.event_time - previous.event_time).total_seconds()
                await self.clock.wait_event_delta(delta, self.speed)
                await self.clock.wait_until_running()
            yield event
            previous = event

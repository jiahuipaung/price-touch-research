from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from price_touch.config import MatrixConfig, Settings
from price_touch.domain import MarketEvent
from price_touch.live import LiveRuntime
from price_touch.model.engine import ModelResult
from price_touch.model.types import ProbabilityMatrix
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore


class ConstantEngine:
    def forecast(self, geometry, state, *, forecast_id, calibrator=None):
        shape = (len(geometry.intervals), len(geometry.windows))
        baseline = ProbabilityMatrix(np.full(shape, 0.2), "BASELINE")
        raw = ProbabilityMatrix(np.full(shape, 0.3), "RAW", path_count=32)
        calibrated = ProbabilityMatrix(np.full(shape, 0.25), "CALIBRATED", path_count=32)
        return ModelResult(baseline, raw, calibrated, [], 32)


class OneEventThenWaitAdapter:
    def __init__(self, event: MarketEvent) -> None:
        self.event = event

    async def events(self) -> AsyncIterator[MarketEvent]:
        yield self.event
        await asyncio.Event().wait()


class StopRuntime(Exception):
    pass


@pytest.mark.asyncio
async def test_live_runtime_publishes_each_tick_without_waiting_for_another_trade() -> None:
    start = datetime(2026, 10, 22, tzinfo=UTC)
    event = MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=start,
        received_time=start,
        price_ticks=10_000_000,
        trade_id="binance:BTCUSDT:1",
    )
    settings = Settings(
        data_mode="LIVE",
        matrix=MatrixConfig(interval_count=3, window_count=2),
        monte_carlo_paths=100,
    )
    store = SnapshotStore()
    service = ForecastService(
        settings=settings,
        store=store,
        engine=ConstantEngine(),
        provider="Binance Spot",
    )
    times = iter((start + timedelta(seconds=1), start + timedelta(seconds=2)))
    sleep_count = 0

    async def stop_after_two_ticks(_: float) -> None:
        nonlocal sleep_count
        sleep_count += 1
        if sleep_count == 2:
            raise StopRuntime
        await asyncio.sleep(0)

    runtime = LiveRuntime(
        service,
        adapter_factory=lambda: OneEventThenWaitAdapter(event),
        clock=lambda: next(times),
        sleep=stop_after_two_ticks,
        reconnect_attempts=1,
    )

    with pytest.raises(StopRuntime):
        await runtime.run()

    snapshots = store.list_snapshots()
    assert len(snapshots) == 2
    assert [snapshot.origin_time for snapshot in snapshots] == [
        start + timedelta(seconds=1),
        start + timedelta(seconds=2),
    ]
    assert all(snapshot.source.mode.value == "LIVE" for snapshot in snapshots)

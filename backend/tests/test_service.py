from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from price_touch.config import MatrixConfig, Settings
from price_touch.domain import EventKind, MarketEvent, QualityFlag
from price_touch.model.engine import ModelResult
from price_touch.model.types import ProbabilityMatrix
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore


class ConstantEngine:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def forecast(self, geometry, state, *, forecast_id, calibrator=None):
        if self.fail:
            return None
        shape = (len(geometry.intervals), len(geometry.windows))
        baseline = ProbabilityMatrix(np.full(shape, 0.2), "BASELINE")
        raw = ProbabilityMatrix(np.full(shape, 0.3), "RAW", path_count=32)
        calibrated = ProbabilityMatrix(np.full(shape, 0.25), "CALIBRATED", path_count=32)
        return ModelResult(baseline, raw, calibrated, [], 32)


def event(second: int, price: int = 5_000_000, trade_id: str | None = None) -> MarketEvent:
    when = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=second)
    return MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=when,
        received_time=when,
        price_ticks=price,
        trade_id=trade_id or str(second),
        kind=EventKind.TRADE,
    )


def settings() -> Settings:
    matrix = MatrixConfig(
        interval_count=3,
        window_count=2,
        observation_delay_seconds=1,
        window_seconds=1,
    )
    return Settings(matrix=matrix)


@pytest.mark.asyncio
async def test_complete_snapshots_are_atomic_and_slow_subscribers_do_not_block() -> None:
    store = SnapshotStore()
    service = ForecastService(settings=settings(), store=store, engine=ConstantEngine())
    subscriber = store.subscribe()
    for second in range(4):
        service.ingest(event(second))
        snapshot = await service.publish(event(second).event_time)
        assert snapshot is not None

    assert len(store.list_snapshots()) == 4
    assert subscriber.qsize() == 1
    latest = subscriber.get_nowait()
    assert latest.forecast_id == store.latest().forecast_id
    assert len(latest.matrices.calibrated) == 3
    assert all(len(row) == 2 for row in latest.matrices.calibrated)


@pytest.mark.asyncio
async def test_failed_matrix_is_never_persisted_or_republished() -> None:
    store = SnapshotStore()
    engine = ConstantEngine()
    service = ForecastService(settings=settings(), store=store, engine=engine)
    service.ingest(event(0))
    first = await service.publish(event(0).event_time)
    engine.fail = True
    service.ingest(event(1))
    failed = await service.publish(event(1).event_time)

    assert first is not None
    assert failed is None
    assert [item.forecast_id for item in store.list_snapshots()] == [first.forecast_id]


@pytest.mark.asyncio
async def test_matured_label_uses_frozen_forecast_geometry() -> None:
    store = SnapshotStore()
    service = ForecastService(settings=settings(), store=store, engine=ConstantEngine())
    service.ingest(event(0))
    snapshot = await service.publish(event(0).event_time)
    assert snapshot is not None
    center = snapshot.intervals[1]
    service.ingest(event(1, center.lower_ticks))
    service.ingest(event(2, center.upper_ticks - 1))
    labels = service.mature(event(3).event_time)

    assert len(labels) == 1
    record = store.get_record(snapshot.forecast_id)
    assert record.label is not None
    assert record.label.values[1] == [1, 1]
    assert record.label.precision.value == "TICK_EXACT"
    assert QualityFlag.BAR_APPROX not in record.label.quality_flags

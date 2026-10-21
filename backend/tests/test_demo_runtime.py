from datetime import UTC, datetime, timedelta

import pytest
from price_touch.config import MatrixConfig, Settings
from price_touch.demo import DemoRuntime
from price_touch.model.engine import ProbabilityEngine
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore


@pytest.mark.asyncio
async def test_demo_runtime_exposes_fault_then_recovery_with_advancing_snapshots() -> None:
    settings = Settings(
        matrix=MatrixConfig(interval_count=3, window_count=2),
        monte_carlo_paths=100,
    )
    store = SnapshotStore()
    service = ForecastService(
        settings=settings,
        store=store,
        engine=ProbabilityEngine(primary_path_count=100, reduced_path_count=100),
    )
    runtime = DemoRuntime(service, fault_step=2)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    for step in range(4):
        await runtime.step(start + timedelta(seconds=step))

    snapshots = store.list_snapshots()
    assert [item.source.message for item in snapshots] == ["HEALTHY", "HEALTHY", "SOURCE_ERROR", "HEALTHY"]
    assert len({item.forecast_id for item in snapshots}) == 4

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from price_touch.config import MatrixConfig, Settings
from price_touch.domain import (
    ForecastSnapshot,
    IntervalBounds,
    MatrixPayload,
    QualityFlag,
    SourceMode,
    SourceStatus,
    WindowBounds,
)
from price_touch.live import LiveRuntime
from price_touch.main import build_runtime
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore
from pydantic import ValidationError


def test_default_settings_describe_the_acceptance_matrix() -> None:
    settings = Settings()

    assert settings.matrix.interval_count == 21
    assert settings.matrix.window_count == 36
    assert settings.matrix.observation_delay_seconds == 5
    assert settings.matrix.window_seconds == 5
    assert settings.publication_interval_seconds == 1
    assert set(settings.assets) == {"BTC", "GOLD", "OIL"}
    assert all(asset.tick_size > 0 for asset in settings.assets.values())


def test_live_mode_builds_a_binance_live_runtime() -> None:
    settings = Settings(data_mode="LIVE")
    service = ForecastService(settings=settings, store=SnapshotStore())

    runtime = build_runtime(settings, service)

    assert isinstance(runtime, LiveRuntime)
    assert all(asset.step_ticks > 0 for asset in settings.assets.values())


@pytest.mark.parametrize(
    "overrides",
    [
        {"interval_count": 2},
        {"interval_count": 201},
        {"window_count": 0},
        {"window_count": 121},
        {"window_seconds": 0},
    ],
)
def test_matrix_config_rejects_unsafe_sizes(overrides: dict[str, int]) -> None:
    with pytest.raises(ValidationError):
        MatrixConfig(**overrides)


def test_forecast_snapshot_serializes_explicit_provenance_and_frozen_geometry() -> None:
    now = datetime(2026, 10, 21, tzinfo=UTC)
    snapshot = ForecastSnapshot(
        schema_version="1.0",
        forecast_id="btc-1761000000",
        asset="BTC",
        instrument="BTCUSDT",
        origin_time=now,
        published_at=now,
        origin_price_ticks=10_000,
        intervals=[IntervalBounds(index=0, lower_ticks=9_950, upper_ticks=10_050)],
        windows=[WindowBounds(index=0, start_ns=5_000_000_000, end_ns=10_000_000_000)],
        matrices=MatrixPayload(baseline=[[0.2]], raw=[[0.3]], calibrated=[[0.25]]),
        source=SourceStatus(
            mode=SourceMode.REPLAY,
            provider="demo",
            age_seconds=0.0,
            last_event_time=now,
            stale=False,
            market_closed=False,
        ),
        model_version="hybrid-v1",
        regime="MEDIUM",
        path_count=2_000,
        compute_duration_ms=12.5,
        quality_flags=[QualityFlag.UNCALIBRATED],
    )

    payload = snapshot.model_dump(mode="json")

    assert payload["source"]["mode"] == "REPLAY"
    assert payload["source"]["stale"] is False
    assert payload["model_version"] == "hybrid-v1"
    assert payload["intervals"] == [{"index": 0, "lower_ticks": 9950, "upper_ticks": 10050}]
    assert payload["windows"] == [{"index": 0, "start_ns": 5_000_000_000, "end_ns": 10_000_000_000}]
    assert len(payload["matrices"]["calibrated"]) == 1
    assert len(payload["matrices"]["calibrated"][0]) == 1

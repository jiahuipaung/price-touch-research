from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import price_touch.backtest.runner as runner_module
from price_touch.backtest.runner import BacktestConfig, WalkForwardRunner
from price_touch.config import MatrixConfig
from price_touch.domain import MarketEvent
from price_touch.model.engine import ModelResult
from price_touch.model.types import ProbabilityMatrix

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def events(through_second: int, *, sentinel_at: int | None = None) -> list[MarketEvent]:
    result = []
    for second in range(through_second + 1):
        price = 100_000 + second * 10
        if sentinel_at == second:
            price = 9_999_999
        timestamp = BASE + timedelta(seconds=second)
        result.append(
            MarketEvent(
                asset="BTC",
                instrument="BTCUSDT",
                event_time=timestamp,
                received_time=timestamp,
                price_ticks=price,
                trade_id=str(second),
            )
        )
    return result


class RecordingEngine:
    def __init__(self) -> None:
        self.calls = []

    def forecast(self, geometry, state, *, forecast_id: str, calibrator=None):
        self.calls.append((forecast_id, state, calibrator))
        shape = (len(geometry.intervals), len(geometry.windows))
        baseline = ProbabilityMatrix(np.full(shape, 0.2), "BASELINE")
        raw = ProbabilityMatrix(np.full(shape, 0.3), "RAW", path_count=10, simulation_batches=1)
        calibrated_values = calibrator.apply_many(raw.values) if calibrator else raw.values
        calibrated = ProbabilityMatrix(calibrated_values, "CALIBRATED", path_count=10, simulation_batches=1)
        return ModelResult(baseline, raw, calibrated, [], 10)


def config() -> BacktestConfig:
    return BacktestConfig(
        asset="BTC",
        instrument="BTCUSDT",
        step_ticks=200,
        origin_cadence_seconds=5,
        warmup_seconds=5,
        matrix=MatrixConfig(
            interval_count=3,
            window_count=1,
            observation_delay_seconds=1,
            window_seconds=5,
        ),
    )


def test_origins_follow_five_second_cadence_and_future_sentinel_cannot_change_first_forecast() -> None:
    base_engine = RecordingEngine()
    sentinel_engine = RecordingEngine()

    base_run = WalkForwardRunner(base_engine, config()).run(events(20))
    sentinel_run = WalkForwardRunner(sentinel_engine, config()).run(events(99, sentinel_at=99))

    assert [forecast.origin_ns for forecast in base_run.forecasts] == [
        int((BASE + timedelta(seconds=second)).timestamp() * 1_000_000_000) for second in (5, 10, 15, 20)
    ]
    assert base_engine.calls[0][1] == sentinel_engine.calls[0][1]
    assert base_run.forecasts[0].regime == sentinel_run.forecasts[0].regime


def test_labels_appear_only_after_final_window_matures() -> None:
    immature = WalkForwardRunner(RecordingEngine(), config()).run(events(10))
    mature = WalkForwardRunner(RecordingEngine(), config()).run(events(11))

    assert immature.forecasts[0].matures_at_ns == int(
        (BASE + timedelta(seconds=11)).timestamp() * 1_000_000_000
    )
    assert immature.forecasts[0].labels is None
    assert mature.forecasts[0].labels is not None


def test_calibrator_at_each_origin_contains_only_already_matured_prior_labels() -> None:
    engine = RecordingEngine()

    WalkForwardRunner(engine, config()).run(events(26))

    for forecast_id, _state, calibrator in engine.calls:
        origin_ns = int(forecast_id.rsplit(":", 1)[1])
        if calibrator.max_matured_at_ns is not None:
            assert calibrator.max_matured_at_ns < origin_ns


def test_runner_bounds_feature_history_and_passes_only_window_events_to_labeler(monkeypatch) -> None:
    observed_label_batch_sizes: list[int] = []
    original = runner_module.label_forecast

    def recording_labeler(geometry, selected_events, precision):
        observed_label_batch_sizes.append(len(selected_events))
        return original(geometry, selected_events, precision)

    monkeypatch.setattr(runner_module, "label_forecast", recording_labeler)
    bounded = replace(config(), feature_lookback_events=3)
    engine = RecordingEngine()
    WalkForwardRunner(engine, bounded).run(events(100))

    assert all(call[1].sample_count <= 2 for call in engine.calls)
    assert observed_label_batch_sizes
    assert max(observed_label_batch_sizes) <= 6

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from fastapi.testclient import TestClient
from price_touch.api import create_app
from price_touch.backtest.metrics import MetricRow, compute_metrics
from price_touch.config import MatrixConfig, Settings
from price_touch.domain import EventKind, MarketEvent
from price_touch.market.clock import ReplayClock
from price_touch.market.quality import DecisionReason
from price_touch.market.replay import ReplayAdapter
from price_touch.model.engine import ModelResult
from price_touch.model.types import ProbabilityMatrix
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore


class DeterministicEngine:
    def forecast(self, geometry, state, *, forecast_id, calibrator=None):
        shape = (len(geometry.intervals), len(geometry.windows))
        baseline = ProbabilityMatrix(np.full(shape, 0.1), "ANALYTIC")
        raw = ProbabilityMatrix(np.full(shape, 0.2), "BOOTSTRAP", path_count=16)
        calibrated = ProbabilityMatrix(np.full(shape, 0.15), "CALIBRATED", path_count=16)
        return ModelResult(baseline, raw, calibrated, [], 16)


def make_event(second: int, price: int, trade_id: str | None = None) -> MarketEvent:
    when = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(seconds=second)
    return MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=when,
        received_time=when,
        price_ticks=price,
        trade_id=trade_id or f"t-{second}",
        kind=EventKind.TRADE,
    )


@pytest.mark.asyncio
async def test_replay_to_api_websocket_export_and_report(tmp_path) -> None:
    settings = Settings(
        matrix=MatrixConfig(
            interval_count=3,
            window_count=2,
            observation_delay_seconds=1,
            window_seconds=1,
        )
    )
    events = [make_event(index, 5_000_000 + index * 10) for index in range(6)]
    store = SnapshotStore(tmp_path / "latest.json")
    service = ForecastService(settings=settings, store=store, engine=DeterministicEngine())
    assert service.ingest(events[0]) is True
    assert service.ingest(events[0]) is False
    assert service.quality_gate.counters[DecisionReason.DUPLICATE] == 1
    adapter = ReplayAdapter(events[1:], clock=ReplayClock.immediate())
    await service.run(adapter)
    service.mature(events[-1].event_time + timedelta(seconds=3))

    records = store.records()
    assert len(records) == 5
    assert all(record.label is not None for record in records)
    persisted = json.loads((tmp_path / "latest.json").read_text())
    assert persisted["forecast_id"] == records[-1].snapshot.forecast_id

    rows: list[MetricRow] = []
    for record in records:
        assert record.label is not None
        for row_index, values in enumerate(record.label.values):
            for column_index, label in enumerate(values):
                rows.append(
                    MetricRow(
                        forecast_id=record.snapshot.forecast_id,
                        asset=record.snapshot.asset,
                        regime=record.snapshot.regime,
                        horizon_bucket=str(column_index),
                        distance_bucket=str(row_index),
                        probability=record.snapshot.matrices.calibrated[row_index][column_index],
                        baseline_probability=record.snapshot.matrices.baseline[row_index][column_index],
                        label=label,
                        label_precision=record.label.precision.value,
                    )
                )
    report = compute_metrics(rows)
    report_dir = tmp_path / "backtests" / "demo"
    report_dir.mkdir(parents=True)
    (report_dir / "summary.json").write_text(json.dumps({"count": report.overall.count}))

    client = TestClient(create_app(store=store, settings=settings, backtest_directory=tmp_path / "backtests"))
    forecast_id = records[-1].snapshot.forecast_id
    assert client.get(f"/api/v1/snapshots/{forecast_id}").status_code == 200
    assert client.get(f"/api/v1/exports/{forecast_id}?format=csv").text.count("\n") == 7
    assert client.get("/api/v1/backtests").json() == [{"count": report.overall.count}]
    with client.websocket_connect("/ws/snapshots") as websocket:
        assert websocket.receive_json()["forecast_id"] == forecast_id

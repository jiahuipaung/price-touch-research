from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from price_touch.api import create_app
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
from price_touch.labeling import LabelPrecision, TouchLabels
from price_touch.storage import SnapshotStore


def snapshot() -> ForecastSnapshot:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return ForecastSnapshot(
        schema_version="1.0",
        forecast_id="BTC-1",
        asset="BTC",
        instrument="BTCUSDT",
        origin_time=now,
        published_at=now,
        origin_price_ticks=5_000_000,
        intervals=[IntervalBounds(index=0, lower_ticks=4_999_950, upper_ticks=5_000_050)],
        windows=[WindowBounds(index=0, start_ns=1_000_000_000, end_ns=2_000_000_000)],
        matrices=MatrixPayload(baseline=[[0.1]], raw=[[0.2]], calibrated=[[0.15]]),
        source=SourceStatus(
            mode=SourceMode.REPLAY,
            provider="demo",
            age_seconds=0,
            last_event_time=now,
            stale=False,
            market_closed=False,
        ),
        model_version="test",
        regime="MEDIUM",
        path_count=100,
        compute_duration_ms=1.2,
        quality_flags=[QualityFlag.UNCALIBRATED],
    )


def client_with_snapshot(*, market_closed: bool = False) -> tuple[TestClient, SnapshotStore]:
    store = SnapshotStore()
    item = snapshot()
    if market_closed:
        item = item.model_copy(
            update={
                "source": item.source.model_copy(update={"market_closed": True}),
                "quality_flags": [QualityFlag.MARKET_CLOSED],
            }
        )
    store.publish(item)
    label = TouchLabels(values=[[1]], precision=LabelPrecision.TICK_EXACT, quality_flags=[])
    store.attach_label(item.forecast_id, label)
    app = create_app(store=store, settings=Settings(matrix=MatrixConfig(interval_count=3, window_count=2)))
    return TestClient(app), store


def test_health_separates_liveness_readiness_and_market_state() -> None:
    client, _ = client_with_snapshot(market_closed=True)
    body = client.get("/api/v1/health").json()
    assert body["live"] is True
    assert body["ready"] is True
    assert body["fresh"] is False
    assert body["state"] == "MARKET_CLOSED"


def test_config_validation_is_actionable() -> None:
    client, _ = client_with_snapshot()
    response = client.put("/api/v1/config", json={"interval_count": 4})
    assert response.status_code == 422
    assert "odd" in response.text


def test_snapshot_and_exports_preserve_frozen_metadata_and_label_precision() -> None:
    client, _ = client_with_snapshot()
    body = client.get("/api/v1/snapshots/BTC-1").json()
    assert body["snapshot"]["intervals"][0]["lower_ticks"] == 4_999_950
    assert body["label"]["precision"] == "TICK_EXACT"
    json_export = client.get("/api/v1/exports/BTC-1?format=json").json()
    assert json_export["snapshot"]["quality_flags"] == ["UNCALIBRATED"]
    csv_response = client.get("/api/v1/exports/BTC-1?format=csv")
    row = next(csv.DictReader(io.StringIO(csv_response.text)))
    assert row["label_precision"] == "TICK_EXACT"
    assert row["interval_lower_ticks"] == "4999950"


def test_websocket_delivers_versioned_full_snapshot() -> None:
    client, _ = client_with_snapshot()
    with client.websocket_connect("/ws/snapshots") as websocket:
        message = websocket.receive_json()
    assert message["schema_version"] == "1.0"
    assert message["forecast_id"] == "BTC-1"
    assert message["matrices"]["calibrated"] == [[0.15]]

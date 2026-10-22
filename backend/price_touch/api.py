from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from price_touch.config import MatrixConfig, Settings
from price_touch.storage import SnapshotRecord, SnapshotStore


def _record_payload(record: SnapshotRecord) -> dict:
    return {
        "snapshot": record.snapshot.model_dump(mode="json"),
        "label": record.label.model_dump(mode="json") if record.label else None,
    }


def _record_csv(record: SnapshotRecord) -> str:
    output = io.StringIO()
    fieldnames = [
        "forecast_id",
        "asset",
        "interval_index",
        "interval_lower_ticks",
        "interval_upper_ticks",
        "window_index",
        "window_start_ns",
        "window_end_ns",
        "baseline",
        "raw",
        "calibrated",
        "label",
        "label_precision",
        "quality_flags",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    snapshot = record.snapshot
    for row_index, interval in enumerate(snapshot.intervals):
        for column_index, window in enumerate(snapshot.windows):
            writer.writerow(
                {
                    "forecast_id": snapshot.forecast_id,
                    "asset": snapshot.asset,
                    "interval_index": interval.index,
                    "interval_lower_ticks": interval.lower_ticks,
                    "interval_upper_ticks": interval.upper_ticks,
                    "window_index": window.index,
                    "window_start_ns": window.start_ns,
                    "window_end_ns": window.end_ns,
                    "baseline": snapshot.matrices.baseline[row_index][column_index],
                    "raw": snapshot.matrices.raw[row_index][column_index],
                    "calibrated": snapshot.matrices.calibrated[row_index][column_index],
                    "label": record.label.values[row_index][column_index] if record.label else "",
                    "label_precision": record.label.precision.value if record.label else "",
                    "quality_flags": "|".join(flag.value for flag in snapshot.quality_flags),
                }
            )
    return output.getvalue()


def create_app(
    *,
    store: SnapshotStore | None = None,
    settings: Settings | None = None,
    backtest_directory: Path | None = None,
    lifespan=None,
    static_directory: Path | None = None,
    transport_status: Callable[[], bool] | None = None,
) -> FastAPI:
    app = FastAPI(title="Price Touch Probability", version="1.0.0", lifespan=lifespan)
    app.state.store = store or SnapshotStore()
    app.state.settings = settings or Settings()
    app.state.backtest_directory = backtest_directory
    app.state.transport_status = transport_status

    @app.get("/api/v1/health")
    def health() -> dict:
        latest = app.state.store.latest()
        ready = latest is not None
        if latest is None:
            transport_ok = transport_status is None or transport_status()
            state = "STARTING" if transport_ok else "SOURCE_ERROR"
            return {"live": True, "ready": False, "fresh": False, "state": state}
        if latest.source.market_closed:
            state = "MARKET_CLOSED"
        elif latest.source.stale:
            state = "STALE"
        elif latest.source.message in {"SOURCE_ERROR", "GAP"}:
            state = latest.source.message
        else:
            state = "HEALTHY"
        return {
            "live": True,
            "ready": ready,
            "fresh": state == "HEALTHY",
            "state": state,
            "last_forecast_id": latest.forecast_id,
        }

    @app.get("/api/v1/config")
    def get_config() -> dict:
        return app.state.settings.model_dump(mode="json")

    @app.put("/api/v1/config")
    def put_config(payload: dict) -> dict:
        try:
            matrix = MatrixConfig.model_validate({**app.state.settings.matrix.model_dump(), **payload})
        except ValidationError as error:
            raise HTTPException(status_code=422, detail=json.loads(error.json())) from error
        app.state.settings.matrix = matrix
        return matrix.model_dump(mode="json")

    @app.get("/api/v1/snapshots")
    def snapshots(limit: int = Query(default=100, ge=1, le=10_000)) -> list[dict]:
        return [item.model_dump(mode="json") for item in app.state.store.list_snapshots(limit=limit)]

    @app.get("/api/v1/snapshots/{forecast_id}")
    def snapshot(forecast_id: str) -> dict:
        try:
            return _record_payload(app.state.store.get_record(forecast_id))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error

    @app.get("/api/v1/backtests")
    def backtests() -> list[dict]:
        directory = app.state.backtest_directory
        if directory is None or not directory.exists():
            return []
        return [json.loads(path.read_text()) for path in sorted(directory.glob("*/summary.json"))]

    @app.get("/api/v1/exports/{forecast_id}")
    def export(forecast_id: str, format: str = Query(pattern="^(json|csv)$")):
        try:
            record = app.state.store.get_record(forecast_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        if format == "csv":
            return PlainTextResponse(_record_csv(record), media_type="text/csv")
        return _record_payload(record)

    @app.websocket("/ws/snapshots")
    async def websocket_snapshots(websocket: WebSocket) -> None:
        await websocket.accept()
        queue = app.state.store.subscribe()
        try:
            while True:
                item = await queue.get()
                await websocket.send_json(item.model_dump(mode="json"))
        except WebSocketDisconnect:
            pass
        finally:
            app.state.store.unsubscribe(queue)

    if static_directory is not None and static_directory.exists():
        app.mount("/", StaticFiles(directory=static_directory, html=True), name="frontend")

    return app

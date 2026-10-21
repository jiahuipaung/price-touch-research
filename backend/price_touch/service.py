from __future__ import annotations

import asyncio
import calendar
import time
from datetime import UTC, datetime

from price_touch.config import Settings
from price_touch.domain import (
    ForecastSnapshot,
    MarketEvent,
    MatrixPayload,
    QualityFlag,
    SourceMode,
    SourceStatus,
)
from price_touch.geometry import build_geometry
from price_touch.labeling import LabelPrecision, TouchLabels, label_forecast
from price_touch.market.quality import QualityGate, QualityState
from price_touch.model.engine import ProbabilityEngine
from price_touch.model.features import compute_features
from price_touch.model.regime import classify_regime
from price_touch.storage import SnapshotStore


def datetime_ns(value: datetime) -> int:
    utc = value.astimezone(UTC)
    return calendar.timegm(utc.utctimetuple()) * 1_000_000_000 + utc.microsecond * 1_000


class ForecastService:
    def __init__(
        self,
        *,
        settings: Settings,
        store: SnapshotStore,
        engine: ProbabilityEngine | None = None,
        quality_gate: QualityGate | None = None,
        provider: str = "replay",
    ) -> None:
        self.settings = settings
        self.store = store
        self.engine = engine or ProbabilityEngine(primary_path_count=settings.monte_carlo_paths)
        self.quality_gate = quality_gate or QualityGate()
        self.provider = provider
        self.events: list[MarketEvent] = []
        self.historical_volatilities: list[float] = []
        self.market_open = True
        self.transport_ok = True

    def ingest(self, event: MarketEvent) -> bool:
        decision = self.quality_gate.accept(event)
        if decision.accepted:
            self.events.append(event)
        return decision.accepted

    async def publish(self, origin_time: datetime) -> ForecastSnapshot | None:
        if not self.events:
            return None
        latest = max(self.events, key=lambda item: (item.event_time, item.trade_id))
        asset_config = self.settings.assets.get(latest.asset)
        if asset_config is None:
            return None
        origin_ns = datetime_ns(origin_time)
        state = compute_features(self.events, cutoff_ns=origin_ns)
        if state.latest_price_ticks is None:
            return None
        geometry = build_geometry(
            origin_ns,
            state.latest_price_ticks,
            asset_config.step_ticks,
            self.settings.matrix,
        )
        forecast_id = f"{latest.asset}-{origin_ns}"
        started = time.perf_counter()
        result = self.engine.forecast(geometry, state, forecast_id=forecast_id)
        if result is None:
            return None
        regime = classify_regime(state, self.historical_volatilities)
        if state.sufficient:
            self.historical_volatilities.append(state.robust_scale)
        status = self.quality_gate.status(
            origin_time,
            market_open=self.market_open,
            transport_ok=self.transport_ok,
        )
        flags = list(result.quality_flags)
        if not state.sufficient:
            flags.append(QualityFlag.INSUFFICIENT_HISTORY)
        if status.state is QualityState.STALE:
            flags.append(QualityFlag.STALE)
        if status.state is QualityState.MARKET_CLOSED:
            flags.append(QualityFlag.MARKET_CLOSED)
        degraded = status.state in {QualityState.STALE, QualityState.SOURCE_ERROR}
        source = SourceStatus(
            mode=SourceMode.DEGRADED if degraded else SourceMode(self.settings.data_mode),
            provider=self.provider,
            age_seconds=status.age_seconds or 0,
            last_event_time=status.last_event_time,
            stale=status.state is QualityState.STALE,
            market_closed=status.state is QualityState.MARKET_CLOSED,
            message=status.state.value,
        )
        snapshot = ForecastSnapshot(
            schema_version="1.0",
            forecast_id=forecast_id,
            asset=latest.asset,
            instrument=latest.instrument,
            origin_time=origin_time,
            published_at=datetime.now(UTC),
            origin_price_ticks=geometry.origin_price_ticks,
            intervals=geometry.intervals,
            windows=geometry.windows,
            matrices=MatrixPayload(
                baseline=result.baseline.values.tolist(),
                raw=result.raw.values.tolist(),
                calibrated=result.calibrated.values.tolist(),
            ),
            source=source,
            model_version="bootstrap-v1",
            regime=regime.value,
            path_count=result.path_count,
            compute_duration_ms=(time.perf_counter() - started) * 1_000,
            quality_flags=list(dict.fromkeys(flags)),
        )
        self.store.publish(snapshot)
        return snapshot

    def mature(self, now: datetime) -> list[TouchLabels]:
        now_ns = datetime_ns(now)
        matured: list[TouchLabels] = []
        for record in self.store.records():
            snapshot = record.snapshot
            if record.label is not None or not snapshot.windows:
                continue
            if snapshot.windows[-1].end_ns > now_ns:
                continue
            geometry = {
                "origin_ns": datetime_ns(snapshot.origin_time),
                "origin_price_ticks": snapshot.origin_price_ticks,
                "intervals": snapshot.intervals,
                "windows": snapshot.windows,
            }
            from price_touch.domain import ForecastGeometry

            label = label_forecast(
                ForecastGeometry.model_validate(geometry),
                self.events,
                LabelPrecision.TICK_EXACT,
            )
            self.store.attach_label(snapshot.forecast_id, label)
            matured.append(label)
        return matured

    async def run(self, adapter) -> None:
        last_second: int | None = None
        async for event in adapter.events():
            self.ingest(event)
            second = int(event.event_time.timestamp())
            if second != last_second:
                await self.publish(event.event_time)
                self.mature(event.event_time)
                last_second = second
            await asyncio.sleep(0)

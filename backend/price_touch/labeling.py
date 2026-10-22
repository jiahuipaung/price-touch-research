from __future__ import annotations

import calendar
from collections.abc import Sequence
from datetime import UTC
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from price_touch.domain import EventKind, ForecastGeometry, MarketEvent, QualityFlag


class LabelPrecision(StrEnum):
    TICK_EXACT = "TICK_EXACT"
    BAR_APPROX = "BAR_APPROX"


class TouchLabels(BaseModel):
    model_config = ConfigDict(frozen=True)

    values: list[list[int]]
    precision: LabelPrecision
    quality_flags: list[QualityFlag]


def _datetime_to_ns(value) -> int:
    utc = value.astimezone(UTC)
    return calendar.timegm(utc.utctimetuple()) * 1_000_000_000 + utc.microsecond * 1_000


def label_forecast(
    geometry: ForecastGeometry,
    events: Sequence[MarketEvent],
    precision: LabelPrecision,
) -> TouchLabels:
    values = [[0 for _ in geometry.windows] for _ in geometry.intervals]

    for event in events:
        event_ns = _datetime_to_ns(event.event_time)
        window_position = next(
            (
                position
                for position, window in enumerate(geometry.windows)
                if window.start_ns <= event_ns < window.end_ns
            ),
            None,
        )
        if window_position is None:
            continue

        if precision is LabelPrecision.BAR_APPROX and event.kind is EventKind.BAR:
            if event.low_ticks is None or event.high_ticks is None:
                continue
            for interval_position, interval in enumerate(geometry.intervals):
                if event.high_ticks >= interval.lower_ticks and event.low_ticks < interval.upper_ticks:
                    values[interval_position][window_position] = 1
            continue

        for interval_position, interval in enumerate(geometry.intervals):
            if interval.lower_ticks <= event.price_ticks < interval.upper_ticks:
                values[interval_position][window_position] = 1
                break

    flags = [QualityFlag.BAR_APPROX] if precision is LabelPrecision.BAR_APPROX else []
    return TouchLabels(values=values, precision=precision, quality_flags=flags)

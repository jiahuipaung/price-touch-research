from __future__ import annotations

from collections.abc import Sequence

from price_touch.config import MatrixConfig
from price_touch.domain import ForecastGeometry, IntervalBounds, WindowBounds

NANOSECONDS_PER_SECOND = 1_000_000_000


def build_geometry(
    origin_ns: int,
    origin_price_ticks: int,
    step_ticks: int,
    config: MatrixConfig,
) -> ForecastGeometry:
    if step_ticks <= 0 or step_ticks % 2:
        raise ValueError("step_ticks must be a positive even integer")
    if origin_price_ticks <= 0:
        raise ValueError("origin_price_ticks must be positive")

    half_width = step_ticks // 2
    half_count = config.interval_count // 2
    intervals = [
        IntervalBounds(
            index=index,
            lower_ticks=origin_price_ticks + index * step_ticks - half_width,
            upper_ticks=origin_price_ticks + index * step_ticks + half_width,
        )
        for index in range(-half_count, half_count + 1)
    ]

    delay_ns = config.observation_delay_seconds * NANOSECONDS_PER_SECOND
    width_ns = config.window_seconds * NANOSECONDS_PER_SECOND
    windows = [
        WindowBounds(
            index=index,
            start_ns=origin_ns + delay_ns + index * width_ns,
            end_ns=origin_ns + delay_ns + (index + 1) * width_ns,
        )
        for index in range(config.window_count)
    ]
    return ForecastGeometry(
        origin_ns=origin_ns,
        origin_price_ticks=origin_price_ticks,
        intervals=intervals,
        windows=windows,
    )


def interval_index_for_price(price_ticks: int, intervals: Sequence[IntervalBounds]) -> int | None:
    for interval in intervals:
        if interval.lower_ticks <= price_ticks < interval.upper_ticks:
            return interval.index
    return None

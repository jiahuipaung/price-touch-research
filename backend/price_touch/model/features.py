from __future__ import annotations

import calendar
import math
from dataclasses import dataclass
from datetime import UTC

import numpy as np

from price_touch.domain import MarketEvent


@dataclass(frozen=True)
class FeatureState:
    cutoff_ns: int
    latest_price_ticks: int | None
    returns: tuple[float, ...]
    robust_drift: float
    robust_scale: float
    max_abs_return: float
    sample_count: int
    sufficient: bool


def event_time_ns(event: MarketEvent) -> int:
    utc = event.event_time.astimezone(UTC)
    return calendar.timegm(utc.utctimetuple()) * 1_000_000_000 + utc.microsecond * 1_000


def compute_features(events: list[MarketEvent], *, cutoff_ns: int) -> FeatureState:
    eligible = sorted(
        (event for event in events if event_time_ns(event) <= cutoff_ns and event.price_ticks > 0),
        key=lambda event: (event.event_time, event.trade_id),
    )
    closes_by_second: dict[int, MarketEvent] = {}
    for event in eligible:
        closes_by_second[event_time_ns(event) // 1_000_000_000] = event
    prices = np.asarray(
        [closes_by_second[second].price_ticks for second in sorted(closes_by_second)],
        dtype=float,
    )
    returns = np.diff(np.log(prices)) if len(prices) >= 2 else np.asarray([], dtype=float)
    if returns.size:
        drift = float(np.median(returns))
        mad = float(np.median(np.abs(returns - drift)))
        scale = 1.4826 * mad
        max_abs = float(np.max(np.abs(returns)))
    else:
        drift = scale = max_abs = 0.0
    if not all(math.isfinite(value) for value in (drift, scale, max_abs)):
        raise ValueError("feature state contains a non-finite value")
    return FeatureState(
        cutoff_ns=cutoff_ns,
        latest_price_ticks=int(prices[-1]) if len(prices) else None,
        returns=tuple(float(value) for value in returns),
        robust_drift=drift,
        robust_scale=scale,
        max_abs_return=max_abs,
        sample_count=int(returns.size),
        sufficient=returns.size >= 2,
    )

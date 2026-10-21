from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from price_touch.domain import MarketEvent
from price_touch.model.features import compute_features
from price_touch.model.regime import Regime, classify_regime

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def events(prices: list[int]) -> list[MarketEvent]:
    return [
        MarketEvent(
            asset="BTC",
            instrument="BTCUSDT",
            event_time=BASE + timedelta(seconds=index),
            received_time=BASE + timedelta(seconds=index),
            price_ticks=price,
            trade_id=str(index),
        )
        for index, price in enumerate(prices)
    ]


def ns_at(seconds: int) -> int:
    return int((BASE + timedelta(seconds=seconds)).timestamp() * 1_000_000_000)


def test_future_sentinel_cannot_change_features_or_regime_at_cutoff() -> None:
    past = events([100_000, 100_100, 100_050, 100_200, 100_150])
    with_future = past + [
        MarketEvent(
            asset="BTC",
            instrument="BTCUSDT",
            event_time=BASE + timedelta(seconds=99),
            received_time=BASE + timedelta(seconds=99),
            price_ticks=9_999_999,
            trade_id="future-sentinel",
        )
    ]

    before = compute_features(past, cutoff_ns=ns_at(4))
    after = compute_features(with_future, cutoff_ns=ns_at(4))

    assert before == after
    assert classify_regime(before, [0.0005, 0.001, 0.002]) is classify_regime(
        after, [0.0005, 0.001, 0.002]
    )


def test_zero_returns_produce_finite_zero_scale_and_low_regime() -> None:
    state = compute_features(events([100_000] * 8), cutoff_ns=ns_at(7))

    assert state.robust_drift == 0
    assert state.robust_scale == 0
    assert math.isfinite(state.robust_scale)
    assert classify_regime(state, [0.001, 0.002, 0.003]) is Regime.LOW


def test_sparse_history_is_explicitly_insufficient() -> None:
    state = compute_features(events([100_000]), cutoff_ns=ns_at(0))

    assert state.sample_count == 0
    assert state.sufficient is False
    assert classify_regime(state, []) is Regime.INSUFFICIENT


def test_extreme_return_is_classified_as_shock() -> None:
    state = compute_features(events([100_000, 100_100, 200_000]), cutoff_ns=ns_at(2))

    assert state.max_abs_return > 0.5
    assert state.sufficient is True
    assert classify_regime(state, [0.001, 0.002, 0.003]) is Regime.SHOCK

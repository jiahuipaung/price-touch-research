from __future__ import annotations

from datetime import datetime, timedelta, timezone

from price_touch.config import MatrixConfig
from price_touch.domain import EventKind, MarketEvent, QualityFlag
from price_touch.geometry import build_geometry
from price_touch.labeling import LabelPrecision, label_forecast

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def trade(seconds: int, price_ticks: int, trade_id: str) -> MarketEvent:
    timestamp = EPOCH + timedelta(seconds=seconds)
    return MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=timestamp,
        received_time=timestamp,
        price_ticks=price_ticks,
        trade_id=trade_id,
    )


def two_window_geometry():
    return build_geometry(
        origin_ns=0,
        origin_price_ticks=1_000,
        step_ticks=200,
        config=MatrixConfig(interval_count=3, window_count=2),
    )


def test_tick_labels_use_half_open_time_and_price_boundaries() -> None:
    labels = label_forecast(
        two_window_geometry(),
        [
            trade(4, 950, "too-early"),
            trade(5, 900, "window-0-left-boundary"),
            trade(6, 950, "repeat-same-cell"),
            trade(10, 1_100, "window-1-and-right-interval"),
            trade(15, 1_150, "too-late"),
        ],
        LabelPrecision.TICK_EXACT,
    )

    assert labels.values == [[0, 0], [1, 0], [0, 1]]
    assert labels.precision is LabelPrecision.TICK_EXACT
    assert labels.quality_flags == []


def test_tick_jump_does_not_fabricate_touch_in_skipped_interval() -> None:
    labels = label_forecast(
        two_window_geometry(),
        [trade(6, 850, "before-jump"), trade(7, 1_150, "after-jump")],
        LabelPrecision.TICK_EXACT,
    )

    assert labels.values == [[1, 0], [0, 0], [1, 0]]


def test_one_tick_path_can_touch_multiple_intervals_but_not_outside_prices() -> None:
    labels = label_forecast(
        two_window_geometry(),
        [trade(6, 850, "low"), trade(7, 950, "middle"), trade(8, 1_250, "high"), trade(9, 1_500, "outside")],
        LabelPrecision.TICK_EXACT,
    )

    assert labels.values == [[1, 0], [1, 0], [1, 0]]


def test_ohlc_range_produces_separately_flagged_approximate_labels() -> None:
    timestamp = EPOCH + timedelta(seconds=6)
    bar = MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=timestamp,
        received_time=timestamp,
        price_ticks=1_000,
        trade_id="bar-1",
        kind=EventKind.BAR,
        low_ticks=890,
        high_ticks=1_110,
    )

    labels = label_forecast(two_window_geometry(), [bar], LabelPrecision.BAR_APPROX)

    assert labels.values == [[1, 0], [1, 0], [1, 0]]
    assert labels.precision is LabelPrecision.BAR_APPROX
    assert labels.quality_flags == [QualityFlag.BAR_APPROX]

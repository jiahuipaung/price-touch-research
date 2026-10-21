from __future__ import annotations

import pytest
from price_touch.config import MatrixConfig
from price_touch.geometry import build_geometry, interval_index_for_price


def test_build_geometry_freezes_centered_adjacent_intervals_and_disjoint_windows() -> None:
    origin_ns = 1_000_000_000_000
    geometry = build_geometry(
        origin_ns=origin_ns,
        origin_price_ticks=100_000,
        step_ticks=200,
        config=MatrixConfig(),
    )

    assert len(geometry.intervals) == 21
    assert geometry.intervals[0].index == -10
    assert geometry.intervals[0].lower_ticks == 97_900
    assert geometry.intervals[10].index == 0
    assert geometry.intervals[10].lower_ticks == 99_900
    assert geometry.intervals[10].upper_ticks == 100_100
    assert geometry.intervals[-1].upper_ticks == 102_100
    assert all(
        left.upper_ticks == right.lower_ticks
        for left, right in zip(geometry.intervals, geometry.intervals[1:], strict=False)
    )

    assert len(geometry.windows) == 36
    assert geometry.windows[0].start_ns == origin_ns + 5_000_000_000
    assert geometry.windows[0].end_ns == origin_ns + 10_000_000_000
    assert geometry.windows[-1].start_ns == origin_ns + 180_000_000_000
    assert geometry.windows[-1].end_ns == origin_ns + 185_000_000_000
    assert all(
        left.end_ns == right.start_ns
        for left, right in zip(geometry.windows, geometry.windows[1:], strict=False)
    )


def test_shared_price_boundary_belongs_only_to_right_interval() -> None:
    geometry = build_geometry(0, 100_000, 200, MatrixConfig(interval_count=3, window_count=1))

    assert interval_index_for_price(99_900, geometry.intervals) == 0
    assert interval_index_for_price(100_100, geometry.intervals) == 1


def test_odd_step_ticks_are_rejected_because_center_cannot_be_exact() -> None:
    with pytest.raises(ValueError, match="step_ticks must be a positive even integer"):
        build_geometry(0, 100_000, 201, MatrixConfig())

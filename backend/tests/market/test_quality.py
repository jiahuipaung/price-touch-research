from __future__ import annotations

from datetime import datetime, timedelta, timezone

from price_touch.domain import MarketEvent
from price_touch.market.quality import DecisionReason, QualityGate, QualityState

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def event(
    offset_seconds: float,
    trade_id: str,
    *,
    price_ticks: int = 100_000,
    received_delay_seconds: float = 0,
) -> MarketEvent:
    event_time = BASE + timedelta(seconds=offset_seconds)
    return MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=event_time,
        received_time=event_time + timedelta(seconds=received_delay_seconds),
        price_ticks=price_ticks,
        trade_id=trade_id,
    )


def test_stable_trade_id_duplicate_is_rejected_and_counted() -> None:
    gate = QualityGate(max_lateness_seconds=2)

    assert gate.accept(event(1, "same")).accepted is True
    decision = gate.accept(event(2, "same"))

    assert decision.accepted is False
    assert decision.reason is DecisionReason.DUPLICATE
    assert gate.counters[DecisionReason.DUPLICATE] == 1


def test_in_window_reordering_is_accepted_but_too_late_event_is_quarantined() -> None:
    gate = QualityGate(max_lateness_seconds=2)
    gate.accept(event(10, "latest"))

    reordered = gate.accept(event(9, "reordered"))
    gate.finalize_through(BASE + timedelta(seconds=9, milliseconds=500))
    too_late = gate.accept(event(9, "after-finalization"))

    assert reordered.accepted is True
    assert reordered.reordered is True
    assert too_late.accepted is False
    assert too_late.reason is DecisionReason.TOO_LATE
    assert gate.counters[DecisionReason.REORDERED] == 1
    assert gate.counters[DecisionReason.TOO_LATE] == 1


def test_nonpositive_price_is_quarantined_by_quality_gate() -> None:
    gate = QualityGate()

    decision = gate.accept(event(1, "bad-price", price_ticks=0))

    assert decision.accepted is False
    assert decision.reason is DecisionReason.INVALID_PRICE


def test_gap_stale_and_recovery_are_deterministic() -> None:
    gate = QualityGate(gap_after_seconds=2, stale_after_seconds=5)
    gate.accept(event(0, "first"))

    assert gate.status(BASE + timedelta(seconds=1)).state is QualityState.HEALTHY
    assert gate.status(BASE + timedelta(seconds=3)).state is QualityState.GAP
    assert gate.status(BASE + timedelta(seconds=6)).state is QualityState.STALE

    recovered = gate.accept(event(7, "recovery"))

    assert recovered.accepted is True
    assert gate.status(BASE + timedelta(seconds=7, milliseconds=500)).state is QualityState.HEALTHY


def test_clock_skew_is_visible_without_dropping_an_otherwise_valid_trade() -> None:
    gate = QualityGate(clock_skew_seconds=2)

    decision = gate.accept(event(1, "skewed", received_delay_seconds=3))

    assert decision.accepted is True
    assert decision.clock_skew is True
    assert gate.counters[DecisionReason.CLOCK_SKEW] == 1


def test_market_closed_is_distinct_from_transport_failure() -> None:
    gate = QualityGate()

    closed = gate.status(BASE, market_open=False, transport_ok=True)
    failed = gate.status(BASE, market_open=True, transport_ok=False)

    assert closed.state is QualityState.MARKET_CLOSED
    assert failed.state is QualityState.SOURCE_ERROR
    assert closed.state is not failed.state

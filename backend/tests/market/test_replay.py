from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from price_touch.domain import MarketEvent
from price_touch.market.clock import ReplayClock
from price_touch.market.manifest import DemoManifest
from price_touch.market.replay import ReplayAdapter
from pydantic import ValidationError

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def event(offset_seconds: int, trade_id: str, price_ticks: int = 100_000) -> MarketEvent:
    timestamp = BASE + timedelta(seconds=offset_seconds)
    return MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=timestamp,
        received_time=timestamp,
        price_ticks=price_ticks,
        trade_id=trade_id,
    )


async def collect(adapter: ReplayAdapter) -> list[MarketEvent]:
    return [item async for item in adapter.events()]


@pytest.mark.asyncio
async def test_same_fixture_and_seed_emit_identical_order_and_timestamps() -> None:
    fixture = [event(2, "c"), event(0, "a"), event(1, "b")]

    first = await collect(ReplayAdapter(fixture, seed=42, clock=ReplayClock.immediate()))
    second = await collect(ReplayAdapter(fixture, seed=42, clock=ReplayClock.immediate()))

    assert [(item.trade_id, item.event_time) for item in first] == [
        ("a", BASE),
        ("b", BASE + timedelta(seconds=1)),
        ("c", BASE + timedelta(seconds=2)),
    ]
    assert first == second


@pytest.mark.asyncio
async def test_replay_speed_changes_wait_only_not_event_time() -> None:
    waits_at_normal_speed: list[float] = []
    waits_at_fast_speed: list[float] = []

    async def normal_sleep(seconds: float) -> None:
        waits_at_normal_speed.append(seconds)

    async def fast_sleep(seconds: float) -> None:
        waits_at_fast_speed.append(seconds)

    fixture = [event(0, "a"), event(2, "b")]
    normal = await collect(ReplayAdapter(fixture, speed=1, clock=ReplayClock(normal_sleep)))
    fast = await collect(ReplayAdapter(fixture, speed=4, clock=ReplayClock(fast_sleep)))

    assert [item.event_time for item in normal] == [item.event_time for item in fast]
    assert waits_at_normal_speed == [2.0]
    assert waits_at_fast_speed == [0.5]


@pytest.mark.asyncio
async def test_pause_and_resume_never_duplicate_an_event() -> None:
    adapter = ReplayAdapter(
        [event(0, "a"), event(1, "b"), event(2, "c")],
        clock=ReplayClock.immediate(),
    )
    stream = adapter.events()

    first = await anext(stream)
    adapter.pause()
    pending = asyncio.create_task(anext(stream))
    await asyncio.sleep(0)
    assert pending.done() is False

    adapter.resume()
    second = await pending
    third = await anext(stream)

    assert [first.trade_id, second.trade_id, third.trade_id] == ["a", "b", "c"]
    with pytest.raises(StopAsyncIteration):
        await anext(stream)


def test_demo_manifest_requires_complete_provenance() -> None:
    valid = {
        "asset": "BTC",
        "instrument": "BTCUSDT",
        "source_kind": "DETERMINISTIC_SYNTHETIC",
        "source_url": None,
        "acquired_at": "2026-10-21T00:00:00Z",
        "start_time": "2026-01-01T00:00:00Z",
        "end_time": "2026-01-01T00:01:00Z",
        "resolution": "1s trades",
        "label_precision": "TICK_EXACT",
        "row_count": 61,
        "missing_rate": 0.0,
        "sha256": "a" * 64,
        "file": "market_events.csv",
    }

    assert DemoManifest.model_validate(valid).row_count == 61
    for required in (
        "source_kind",
        "start_time",
        "end_time",
        "resolution",
        "label_precision",
        "row_count",
        "sha256",
    ):
        incomplete = valid | {required: None}
        with pytest.raises(ValidationError):
            DemoManifest.model_validate(incomplete)

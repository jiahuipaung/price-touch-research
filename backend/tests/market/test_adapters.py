from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from price_touch.domain import EventKind, MarketEvent, SourceMode
from price_touch.market import binance
from price_touch.market.binance import parse_binance_klines, parse_binance_trade
from price_touch.market.commodities import parse_gold_quote, parse_oil_quote
from price_touch.market.supervisor import AdapterSupervisor, AdapterUnavailable

RECEIVED = datetime(2026, 10, 21, 8, 33, 1, tzinfo=UTC)


def test_binance_tls_context_loads_a_portable_ca_bundle() -> None:
    context = binance.binance_ssl_context()

    assert isinstance(context, ssl.SSLContext)
    assert context.cert_store_stats()["x509_ca"] > 0


def test_binance_trade_fixture_normalizes_trade_timestamp_price_and_stable_id() -> None:
    payload = {
        "e": "trade",
        "E": 1_672_515_782_136,
        "s": "BTCUSDT",
        "t": 12_345,
        "p": "40123.45",
        "q": "0.01",
        "T": 1_672_515_782_000,
        "m": True,
        "M": True,
    }

    event = parse_binance_trade(payload, received_at=RECEIVED, tick_size=Decimal("0.01"))
    duplicate = parse_binance_trade(payload, received_at=RECEIVED, tick_size=Decimal("0.01"))

    assert event.asset == "BTC"
    assert event.instrument == "BTCUSDT"
    assert event.event_time == datetime(2022, 12, 31, 19, 43, 2, tzinfo=UTC)
    assert event.received_time == RECEIVED
    assert event.price_ticks == 4_012_345
    assert event.trade_id == "binance:BTCUSDT:12345"
    assert duplicate.trade_id == event.trade_id
    assert event.kind is EventKind.TRADE


def test_binance_second_klines_become_chronological_warmup_bars() -> None:
    payload = [
        [
            1_672_515_781_000,
            "40100.00",
            "40120.00",
            "40090.00",
            "40110.00",
            "1.0",
            1_672_515_781_999,
            "0",
            4,
            "0",
            "0",
            "0",
        ],
        [
            1_672_515_782_000,
            "40110.00",
            "40130.00",
            "40100.00",
            "40125.00",
            "1.0",
            1_672_515_782_999,
            "0",
            5,
            "0",
            "0",
            "0",
        ],
    ]

    events = parse_binance_klines(payload, received_at=RECEIVED, tick_size=Decimal("0.01"))

    assert [event.price_ticks for event in events] == [4_011_000, 4_012_500]
    assert [event.low_ticks for event in events] == [4_009_000, 4_010_000]
    assert [event.high_ticks for event in events] == [4_012_000, 4_013_000]
    assert all(event.kind is EventKind.BAR for event in events)
    assert events[0].event_time < events[1].event_time


def test_gold_quote_fixture_is_explicitly_delayed_and_uses_provider_timestamp() -> None:
    payload = {
        "xau": {"price": 4123.0, "currency": "USD", "unit": "troy_oz"},
        "updated_at": "2026-10-21T08:33:00.259Z",
        "data_state": {
            "status": "fresh",
            "as_of": "2026-10-21T08:33:00.259Z",
            "source": "upstream",
            "age_seconds": 0,
        },
        "stale": False,
        "source": "xaus.com",
    }

    quote = parse_gold_quote(payload, received_at=RECEIVED, tick_size=Decimal("0.01"))

    assert quote.mode is SourceMode.DELAYED
    assert quote.event.asset == "GOLD"
    assert quote.event.instrument == "XAUUSD"
    assert quote.event.price_ticks == 412_300
    assert quote.event.event_time == datetime(2026, 10, 21, 8, 33, 0, 259000, tzinfo=UTC)
    assert quote.event.kind is EventKind.QUOTE
    assert quote.stale is False


def test_oil_quote_fixture_maps_wti_session_semantics_without_claiming_a_trade() -> None:
    payload = {
        "lastUpdated": "2026-10-20T20:53:41.368Z",
        "observedAt": "2026-10-20T20:43:37.000Z",
        "sessionDate": "2026-10-20",
        "quoteType": "intraday",
        "basis": "session",
        "quoteStatus": "current",
        "provider": "Yahoo Finance (CL=F)",
        "priceUsd": 98.23,
    }

    quote = parse_oil_quote(payload, received_at=RECEIVED, tick_size=Decimal("0.001"))

    assert quote.mode is SourceMode.DELAYED
    assert quote.event.asset == "OIL"
    assert quote.event.instrument == "WTIUSD"
    assert quote.event.price_ticks == 98_230
    assert quote.event.event_time == datetime(2026, 10, 20, 20, 43, 37, tzinfo=UTC)
    assert quote.event.kind is EventKind.QUOTE
    assert quote.provider == "AmericasOilWatch / Yahoo Finance (CL=F)"


class FailingAdapter:
    def __init__(self, error: Exception) -> None:
        self.error = error

    async def events(self) -> AsyncIterator[MarketEvent]:
        raise self.error
        yield  # pragma: no cover


class OneEventAdapter:
    def __init__(self, result: MarketEvent) -> None:
        self.result = result

    async def events(self) -> AsyncIterator[MarketEvent]:
        yield self.result


def sample_event() -> MarketEvent:
    return MarketEvent(
        asset="BTC",
        instrument="BTCUSDT",
        event_time=RECEIVED,
        received_time=RECEIVED,
        price_ticks=100,
        trade_id="one",
    )


@pytest.mark.asyncio
async def test_supervisor_reconnects_with_bounded_exponential_backoff() -> None:
    attempts = 0
    waits: list[float] = []

    def factory():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            return FailingAdapter(ConnectionError(f"attempt {attempts}"))
        return OneEventAdapter(sample_event())

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    supervisor = AdapterSupervisor(
        factory,
        max_attempts=4,
        base_backoff_seconds=1,
        max_backoff_seconds=2,
        sleep=sleep,
    )
    received = [item async for item in supervisor.run()]

    assert received == [sample_event()]
    assert attempts == 3
    assert waits == [1, 2]
    assert supervisor.terminal_error is None


@pytest.mark.asyncio
async def test_supervisor_reports_transport_failure_and_recovery() -> None:
    attempts = 0
    transport_states: list[bool] = []

    def factory():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return FailingAdapter(ConnectionError("temporary outage"))
        return OneEventAdapter(sample_event())

    async def no_sleep(_: float) -> None:
        return None

    supervisor = AdapterSupervisor(
        factory,
        max_attempts=2,
        sleep=no_sleep,
        on_transport_change=transport_states.append,
    )

    received = [item async for item in supervisor.run()]

    assert received == [sample_event()]
    assert transport_states == [False, True]


@pytest.mark.asyncio
async def test_supervisor_reconnects_when_a_live_stream_closes_normally() -> None:
    attempts = 0
    waits: list[float] = []

    def factory():
        nonlocal attempts
        attempts += 1
        return OneEventAdapter(
            sample_event().model_copy(update={"trade_id": f"event-{attempts}"})
        )

    async def no_sleep(seconds: float) -> None:
        waits.append(seconds)

    supervisor = AdapterSupervisor(
        factory,
        max_attempts=3,
        sleep=no_sleep,
        restart_on_completion=True,
    )
    stream = supervisor.run()

    first = await anext(stream)
    second = await anext(stream)
    await stream.aclose()

    assert [first.trade_id, second.trade_id] == ["event-1", "event-2"]
    assert attempts == 2
    assert waits == [1]


@pytest.mark.asyncio
async def test_supervisor_exposes_terminal_failure_without_switching_to_replay() -> None:
    waits: list[float] = []

    async def sleep(seconds: float) -> None:
        waits.append(seconds)

    supervisor = AdapterSupervisor(
        lambda: FailingAdapter(ConnectionError("offline")),
        max_attempts=3,
        base_backoff_seconds=1,
        max_backoff_seconds=4,
        sleep=sleep,
    )

    with pytest.raises(AdapterUnavailable, match="offline"):
        _ = [item async for item in supervisor.run()]

    assert waits == [1, 2]
    assert isinstance(supervisor.terminal_error, ConnectionError)

from __future__ import annotations

import json
import ssl
from datetime import UTC, datetime
from decimal import Decimal

import certifi
import httpx

from price_touch.domain import EventKind, MarketEvent

BINANCE_MARKET_STREAM_BASE = "wss://data-stream.binance.vision/ws"
BINANCE_MARKET_DATA_BASE = "https://data-api.binance.vision"


def binance_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context(cafile=certifi.where())


def _price_to_ticks(value: str | float, tick_size: Decimal) -> int:
    ticks = Decimal(str(value)) / tick_size
    if ticks != ticks.to_integral_value():
        raise ValueError(f"price {value} is not aligned to tick size {tick_size}")
    return int(ticks)


def parse_binance_trade(
    payload: dict[str, object],
    *,
    received_at: datetime,
    tick_size: Decimal,
) -> MarketEvent:
    if payload.get("e") != "trade":
        raise ValueError("payload is not a Binance trade event")
    symbol = str(payload["s"])
    trade_id = int(payload["t"])
    trade_time_ms = int(payload["T"])
    return MarketEvent(
        asset="BTC",
        instrument=symbol,
        event_time=datetime.fromtimestamp(trade_time_ms / 1000, UTC),
        received_time=received_at,
        price_ticks=_price_to_ticks(str(payload["p"]), tick_size),
        trade_id=f"binance:{symbol}:{trade_id}",
        kind=EventKind.TRADE,
    )


def parse_binance_klines(
    payload: list[list[object]],
    *,
    received_at: datetime,
    tick_size: Decimal,
) -> list[MarketEvent]:
    events = []
    for row in payload:
        if len(row) < 7:
            raise ValueError("malformed Binance kline")
        open_time_ms = int(row[0])
        close_time_ms = int(row[6])
        events.append(
            MarketEvent(
                asset="BTC",
                instrument="BTCUSDT",
                event_time=datetime.fromtimestamp(close_time_ms / 1000, UTC),
                received_time=received_at,
                price_ticks=_price_to_ticks(str(row[4]), tick_size),
                trade_id=f"binance-kline:BTCUSDT:{open_time_ms}",
                kind=EventKind.BAR,
                low_ticks=_price_to_ticks(str(row[3]), tick_size),
                high_ticks=_price_to_ticks(str(row[2]), tick_size),
            )
        )
    return sorted(events, key=lambda event: (event.event_time, event.trade_id))


async def fetch_binance_second_klines(
    *,
    symbol: str = "BTCUSDT",
    tick_size: Decimal = Decimal("0.01"),
    limit: int = 900,
) -> list[MarketEvent]:
    if not 2 <= limit <= 1_000:
        raise ValueError("warmup kline limit must be between 2 and 1000")
    received_at = datetime.now(UTC)
    async with httpx.AsyncClient(timeout=10, verify=binance_ssl_context()) as client:
        response = await client.get(
            f"{BINANCE_MARKET_DATA_BASE}/api/v3/klines",
            params={"symbol": symbol.upper(), "interval": "1s", "limit": limit},
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, list):
        raise ValueError("malformed Binance kline response")
    closed = [row for row in payload if len(row) >= 7 and int(row[6]) <= int(received_at.timestamp() * 1_000)]
    return parse_binance_klines(closed, received_at=received_at, tick_size=tick_size)


class BinanceTradeAdapter:
    mode = "LIVE"

    def __init__(self, symbol: str = "BTCUSDT", tick_size: Decimal = Decimal("0.01")) -> None:
        self.symbol = symbol.upper()
        self.tick_size = tick_size
        self.url = f"{BINANCE_MARKET_STREAM_BASE}/{self.symbol.lower()}@trade"

    async def events(self):
        from websockets.asyncio.client import connect

        async with connect(
            self.url,
            ping_interval=None,
            close_timeout=5,
            ssl=binance_ssl_context(),
        ) as websocket:
            async for message in websocket:
                yield parse_binance_trade(
                    json.loads(message),
                    received_at=datetime.now(UTC),
                    tick_size=self.tick_size,
                )

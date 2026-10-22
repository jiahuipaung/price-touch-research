from __future__ import annotations

import json
import ssl
from datetime import UTC, datetime
from decimal import Decimal

import certifi

from price_touch.domain import EventKind, MarketEvent

BINANCE_MARKET_STREAM_BASE = "wss://data-stream.binance.vision/ws"


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

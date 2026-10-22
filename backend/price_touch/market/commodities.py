from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import httpx

from price_touch.domain import EventKind, MarketEvent, SourceMode
from price_touch.market.binance import _price_to_ticks

GOLD_URL = "https://xaus.com/api/v1/spot?compact=1"
OIL_URL = "https://americasoilwatch.com/api/v1/wti"


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


@dataclass(frozen=True)
class ParsedQuote:
    event: MarketEvent
    mode: SourceMode
    provider: str
    stale: bool


def parse_gold_quote(
    payload: dict[str, object],
    *,
    received_at: datetime,
    tick_size: Decimal,
) -> ParsedQuote:
    xau = payload["xau"]
    data_state = payload["data_state"]
    if not isinstance(xau, dict) or not isinstance(data_state, dict):
        raise ValueError("malformed XAUS response")
    observed_at = _parse_timestamp(str(data_state["as_of"]))
    stale = bool(payload.get("stale")) or data_state.get("status") != "fresh"
    event = MarketEvent(
        asset="GOLD",
        instrument="XAUUSD",
        event_time=observed_at,
        received_time=received_at,
        price_ticks=_price_to_ticks(xau["price"], tick_size),
        trade_id=f"xaus:{observed_at.isoformat()}",
        kind=EventKind.QUOTE,
    )
    return ParsedQuote(event=event, mode=SourceMode.DELAYED, provider="XAUS", stale=stale)


def parse_oil_quote(
    payload: dict[str, object],
    *,
    received_at: datetime,
    tick_size: Decimal,
) -> ParsedQuote:
    observed_at = _parse_timestamp(str(payload["observedAt"]))
    upstream = str(payload.get("provider", "unknown"))
    event = MarketEvent(
        asset="OIL",
        instrument="WTIUSD",
        event_time=observed_at,
        received_time=received_at,
        price_ticks=_price_to_ticks(payload["priceUsd"], tick_size),
        trade_id=f"americas-oil-watch:{observed_at.isoformat()}",
        kind=EventKind.QUOTE,
    )
    return ParsedQuote(
        event=event,
        mode=SourceMode.DELAYED,
        provider=f"AmericasOilWatch / {upstream}",
        stale=payload.get("quoteStatus") != "current",
    )


FetchJson = Callable[[str], Awaitable[dict[str, object]]]


class CommodityQuoteAdapter:
    mode = SourceMode.DELAYED

    def __init__(
        self,
        asset: str,
        *,
        tick_size: Decimal,
        poll_seconds: float,
        fetch_json: FetchJson | None = None,
    ) -> None:
        if asset not in {"GOLD", "OIL"}:
            raise ValueError("commodity asset must be GOLD or OIL")
        self.asset = asset
        self.tick_size = tick_size
        self.poll_seconds = poll_seconds
        self.url = GOLD_URL if asset == "GOLD" else OIL_URL
        self._fetch_json = fetch_json or self._http_fetch

    async def _http_fetch(self, url: str) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    async def events(self) -> AsyncIterator[MarketEvent]:
        while True:
            received_at = datetime.now(UTC)
            payload = await self._fetch_json(self.url)
            parsed = (
                parse_gold_quote(payload, received_at=received_at, tick_size=self.tick_size)
                if self.asset == "GOLD"
                else parse_oil_quote(payload, received_at=received_at, tick_size=self.tick_size)
            )
            yield parsed.event
            await asyncio.sleep(self.poll_seconds)

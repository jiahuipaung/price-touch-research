from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from price_touch.market.binance import BinanceTradeAdapter
from price_touch.market.commodities import GOLD_URL, OIL_URL, parse_gold_quote, parse_oil_quote


async def probe_http(name: str, url: str, parser, tick_size: Decimal) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            response.raise_for_status()
            parsed = parser(response.json(), received_at=datetime.now(UTC), tick_size=tick_size)
        return {
            "asset": name,
            "ok": True,
            "mode": parsed.mode,
            "provider": parsed.provider,
            "event_time": parsed.event.event_time.isoformat(),
            "stale": parsed.stale,
        }
    except Exception as error:
        return {"asset": name, "ok": False, "error": f"{type(error).__name__}: {error}"}


async def probe_btc() -> dict[str, object]:
    adapter = BinanceTradeAdapter()
    try:
        event = await asyncio.wait_for(anext(adapter.events()), timeout=10)
        return {
            "asset": "BTC",
            "ok": True,
            "mode": "LIVE",
            "provider": "Binance",
            "event_time": event.event_time.isoformat(),
        }
    except Exception as error:
        return {"asset": "BTC", "ok": False, "error": f"{type(error).__name__}: {error}"}


async def main() -> None:
    results = await asyncio.gather(
        probe_btc(),
        probe_http("GOLD", GOLD_URL, parse_gold_quote, Decimal("0.01")),
        probe_http("OIL", OIL_URL, parse_oil_quote, Decimal("0.001")),
    )
    print(json.dumps({"checked_at": datetime.now(UTC).isoformat(), "sources": results}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

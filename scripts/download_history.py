from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx

BINANCE_MONTHLY = "https://data.binance.vision/data/spot/monthly/aggTrades/BTCUSDT"
DUKASCOPY = "https://datafeed.dukascopy.com/datafeed"
DUKASCOPY_SYMBOLS = {"GOLD": "XAUUSD", "OIL": "LIGHTCMDUSD"}


def month_starts(start: date, end: date):
    current = start.replace(day=1)
    while current <= end:
        yield current
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


def candidate_urls(asset: str, start: date, end: date) -> list[str]:
    if asset == "BTC":
        return [
            f"{BINANCE_MONTHLY}/BTCUSDT-aggTrades-{month:%Y-%m}.zip" for month in month_starts(start, end)
        ]
    symbol = DUKASCOPY_SYMBOLS[asset]
    urls = []
    current = start
    while current <= end:
        for hour in range(24):
            path = f"{symbol}/{current:%Y}/{current.month - 1:02d}/{current:%d}/{hour:02d}h_ticks.bi5"
            urls.append(f"{DUKASCOPY}/{path}")
        current += timedelta(days=1)
    return urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public raw history with checksums")
    parser.add_argument("--asset", choices=["BTC", "GOLD", "OIL"], required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end must be on or after --start")

    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for url in candidate_urls(args.asset, args.start, args.end):
            name = url.rsplit("/", 1)[-1]
            destination = args.output / name
            response = client.get(url)
            if response.status_code == 404:
                results.append({"url": url, "status": "MISSING"})
                continue
            response.raise_for_status()
            destination.write_bytes(response.content)
            results.append(
                {
                    "url": url,
                    "status": "DOWNLOADED",
                    "file": destination.name,
                    "bytes": len(response.content),
                    "sha256": hashlib.sha256(response.content).hexdigest(),
                }
            )
    manifest = {
        "asset": args.asset,
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "downloaded_at": datetime.now(UTC).isoformat(),
        "source": "Binance Data Vision" if args.asset == "BTC" else "Dukascopy public datafeed",
        "raw_only": True,
        "files": results,
    }
    (args.output / "download-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()

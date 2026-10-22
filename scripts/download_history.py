from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx
from price_touch.history import normalized_binance_rows

BINANCE_KLINES = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1m"
DUKASCOPY = "https://datafeed.dukascopy.com/datafeed"
DUKASCOPY_SYMBOLS = {"GOLD": "XAUUSD", "OIL": "LIGHTCMDUSD"}


def month_starts(start: date, end: date):
    current = start.replace(day=1)
    while current <= end:
        yield current
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)


def candidate_urls(asset: str, start: date, end: date) -> list[str]:
    if asset == "BTC":
        return [f"{BINANCE_KLINES}/BTCUSDT-1m-{month:%Y-%m}.zip" for month in month_starts(start, end)]
    symbol = DUKASCOPY_SYMBOLS[asset]
    urls = []
    current = start
    while current <= end:
        for hour in range(24):
            path = f"{symbol}/{current:%Y}/{current.month - 1:02d}/{current:%d}/{hour:02d}h_ticks.bi5"
            urls.append(f"{DUKASCOPY}/{path}")
        current += timedelta(days=1)
    return urls


def write_normalized_btc(
    output: Path,
    archives: list[bytes],
    start: date,
    end: date,
    *,
    missing_rate: float = 0,
) -> dict:
    data_path = output / "market_events.csv"
    fieldnames = [
        "asset", "instrument", "event_time", "received_time", "price_ticks",
        "trade_id", "kind", "low_ticks", "high_ticks",
    ]
    count = 0
    first_time: str | None = None
    last_time: str | None = None
    with data_path.open("w", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames)
        writer.writeheader()
        for archive in archives:
            for row in normalized_binance_rows(archive, start, end):
                writer.writerow(row)
                count += 1
                first_time = first_time or row["event_time"]
                last_time = row["event_time"]
    if count < 2 or first_time is None or last_time is None:
        raise ValueError("downloaded archives contained fewer than two eligible bars")
    manifest = {
        "asset": "BTC",
        "instrument": "BTCUSDT",
        "source_kind": "REAL_PUBLIC",
        "source_url": BINANCE_KLINES,
        "acquired_at": datetime.now(UTC).isoformat(),
        "start_time": first_time,
        "end_time": last_time,
        "resolution": "1m OHLC bars",
        "label_precision": "BAR_APPROX",
        "row_count": count,
        "missing_rate": missing_rate,
        "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest(),
        "file": data_path.name,
        "fault_scenarios_file": None,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download public history with checksums and BTC normalization"
    )
    parser.add_argument("--asset", choices=["BTC", "GOLD", "OIL"], required=True)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.end < args.start:
        parser.error("--end must be on or after --start")

    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    archives: list[bytes] = []
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for url in candidate_urls(args.asset, args.start, args.end):
            name = url.rsplit("/", 1)[-1]
            destination = args.output / name
            response = client.get(url)
            if response.status_code == 404:
                results.append({"url": url, "status": "MISSING"})
                continue
            response.raise_for_status()
            destination.write_bytes(response.content)
            if args.asset == "BTC":
                archives.append(response.content)
            results.append({
                "url": url,
                "status": "DOWNLOADED",
                "file": destination.name,
                "bytes": len(response.content),
                "sha256": hashlib.sha256(response.content).hexdigest(),
            })
    missing_count = sum(result["status"] == "MISSING" for result in results)
    missing_rate = missing_count / len(results) if results else 1.0
    normalized = (
        write_normalized_btc(
            args.output,
            archives,
            args.start,
            args.end,
            missing_rate=missing_rate,
        )
        if args.asset == "BTC"
        else None
    )
    manifest = {
        "asset": args.asset,
        "start": args.start.isoformat(),
        "end": args.end.isoformat(),
        "downloaded_at": datetime.now(UTC).isoformat(),
        "source": "Binance Data Vision" if args.asset == "BTC" else "Dukascopy public datafeed",
        "normalized_manifest": "manifest.json" if normalized else None,
        "raw_only": normalized is None,
        "files": results,
    }
    (args.output / "download-manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps({**manifest, "normalized": normalized}, indent=2))


if __name__ == "__main__":
    main()

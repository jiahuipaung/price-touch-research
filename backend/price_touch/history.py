from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal


def price_ticks(value: str, tick_size: Decimal = Decimal("0.01")) -> int:
    return int((Decimal(value) / tick_size).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def normalized_binance_rows(archive: bytes, start: date, end: date):
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        members = [name for name in bundle.namelist() if name.endswith(".csv")]
        if len(members) != 1:
            raise ValueError("Binance archive must contain exactly one CSV")
        with bundle.open(members[0]) as binary:
            source = io.TextIOWrapper(binary, encoding="utf-8", newline="")
            for fields in csv.reader(source):
                if not fields or not fields[0].isdigit():
                    continue
                raw_timestamp = int(fields[0])
                timestamp_divisor = 1_000_000 if raw_timestamp > 100_000_000_000_000 else 1_000
                event_time = datetime.fromtimestamp(raw_timestamp / timestamp_divisor, UTC)
                if not start <= event_time.date() <= end:
                    continue
                timestamp = event_time.isoformat().replace("+00:00", "Z")
                yield {
                    "asset": "BTC",
                    "instrument": "BTCUSDT",
                    "event_time": timestamp,
                    "received_time": timestamp,
                    "price_ticks": price_ticks(fields[4]),
                    "trade_id": f"kline-{raw_timestamp}",
                    "kind": "BAR",
                    "low_ticks": price_ticks(fields[3]),
                    "high_ticks": price_ticks(fields[2]),
                }

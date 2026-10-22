import csv
import io
import zipfile
from datetime import date

from price_touch.history import normalized_binance_rows, price_ticks


def archive_with(rows: list[list[str]]) -> bytes:
    csv_buffer = io.StringIO()
    csv.writer(csv_buffer).writerows(rows)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("BTCUSDT-1m.csv", csv_buffer.getvalue())
    return archive.getvalue()


def test_binance_ohlc_archive_normalizes_to_bar_approx_geometry() -> None:
    data = archive_with(
        [
            ["open_time", "open", "high", "low", "close"],
            ["1577836800000", "7000.00", "7010.50", "6990.25", "7005.75"],
        ]
    )
    rows = list(normalized_binance_rows(data, date(2020, 1, 1), date(2020, 1, 1)))

    assert rows == [
        {
            "asset": "BTC",
            "instrument": "BTCUSDT",
            "event_time": "2020-01-01T00:00:00Z",
            "received_time": "2020-01-01T00:00:00Z",
            "price_ticks": 700_575,
            "trade_id": "kline-1577836800000",
            "kind": "BAR",
            "low_ticks": 699_025,
            "high_ticks": 701_050,
        }
    ]
    assert price_ticks("0.005") == 1

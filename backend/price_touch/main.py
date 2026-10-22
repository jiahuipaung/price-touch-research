from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from price_touch.api import create_app
from price_touch.config import Settings
from price_touch.demo import DemoRuntime
from price_touch.live import LiveRuntime
from price_touch.market.binance import BinanceTradeAdapter, fetch_binance_second_klines
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore

settings = Settings()
store = SnapshotStore(Path(os.getenv("PRICE_TOUCH_SNAPSHOT_PATH", "artifacts/runtime/latest.json")))
provider = "Binance Spot" if settings.data_mode == "LIVE" else "deterministic offline replay"
service = ForecastService(settings=settings, store=store, provider=provider)


def build_runtime(settings: Settings, service: ForecastService):
    if settings.data_mode == "REPLAY":
        return DemoRuntime(service)
    if settings.data_mode == "LIVE":
        btc = settings.assets["BTC"]
        return LiveRuntime(
            service,
            adapter_factory=lambda: BinanceTradeAdapter(symbol=btc.instrument, tick_size=btc.tick_size),
            warmup_loader=lambda: fetch_binance_second_klines(
                symbol=btc.instrument,
                tick_size=btc.tick_size,
            ),
        )
    raise ValueError(f"unsupported data mode: {settings.data_mode}")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    runtime = build_runtime(settings, service)
    task = asyncio.create_task(runtime.run())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


static_directory = Path(os.getenv("PRICE_TOUCH_STATIC_DIR", "frontend/dist"))
backtest_directory = Path(os.getenv("PRICE_TOUCH_BACKTEST_DIR", "artifacts"))
app = create_app(
    store=store,
    settings=settings,
    backtest_directory=backtest_directory,
    lifespan=lifespan,
    static_directory=static_directory,
    transport_status=lambda: service.transport_ok,
)

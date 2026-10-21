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
from price_touch.service import ForecastService
from price_touch.storage import SnapshotStore

settings = Settings()
store = SnapshotStore(Path(os.getenv("PRICE_TOUCH_SNAPSHOT_PATH", "artifacts/runtime/latest.json")))
service = ForecastService(settings=settings, store=store, provider="deterministic offline replay")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    task: asyncio.Task[None] | None = None
    if settings.data_mode == "REPLAY":
        task = asyncio.create_task(DemoRuntime(service).run())
    yield
    if task is not None:
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
)

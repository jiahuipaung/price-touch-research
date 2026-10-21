from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from price_touch.domain import MarketEvent


class MarketAdapter(Protocol):
    def events(self) -> AsyncIterator[MarketEvent]: ...

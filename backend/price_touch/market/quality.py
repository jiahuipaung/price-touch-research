from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from price_touch.domain import MarketEvent


class DecisionReason(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REORDERED = "REORDERED"
    TOO_LATE = "TOO_LATE"
    INVALID_PRICE = "INVALID_PRICE"
    CLOCK_SKEW = "CLOCK_SKEW"


class QualityState(StrEnum):
    STARTING = "STARTING"
    HEALTHY = "HEALTHY"
    GAP = "GAP"
    STALE = "STALE"
    MARKET_CLOSED = "MARKET_CLOSED"
    SOURCE_ERROR = "SOURCE_ERROR"


@dataclass(frozen=True)
class QualityDecision:
    accepted: bool
    reason: DecisionReason
    reordered: bool = False
    clock_skew: bool = False


@dataclass(frozen=True)
class QualityStatus:
    state: QualityState
    age_seconds: float | None
    last_event_time: datetime | None


class QualityGate:
    def __init__(
        self,
        *,
        max_lateness_seconds: float = 2,
        gap_after_seconds: float = 2,
        stale_after_seconds: float = 5,
        clock_skew_seconds: float = 2,
    ) -> None:
        if not max_lateness_seconds >= 0:
            raise ValueError("max_lateness_seconds must be nonnegative")
        if not 0 < gap_after_seconds < stale_after_seconds:
            raise ValueError("freshness thresholds must satisfy 0 < gap < stale")
        self.max_lateness = timedelta(seconds=max_lateness_seconds)
        self.gap_after_seconds = gap_after_seconds
        self.stale_after_seconds = stale_after_seconds
        self.clock_skew_seconds = clock_skew_seconds
        self.counters: Counter[DecisionReason] = Counter()
        self._seen_ids: set[tuple[str, str]] = set()
        self._latest_event_time: datetime | None = None
        self._finalized_through: datetime | None = None

    def finalize_through(self, event_time: datetime) -> None:
        if self._finalized_through is None or event_time > self._finalized_through:
            self._finalized_through = event_time

    def accept(self, event: MarketEvent) -> QualityDecision:
        if event.price_ticks <= 0:
            return self._reject(DecisionReason.INVALID_PRICE)

        identity = (event.instrument, event.trade_id)
        if identity in self._seen_ids:
            return self._reject(DecisionReason.DUPLICATE)

        watermark = self._finalized_through
        if self._latest_event_time is not None:
            automatic = self._latest_event_time - self.max_lateness
            watermark = automatic if watermark is None else max(watermark, automatic)
        if watermark is not None and event.event_time <= watermark:
            return self._reject(DecisionReason.TOO_LATE)

        reordered = self._latest_event_time is not None and event.event_time < self._latest_event_time
        skew = abs((event.received_time - event.event_time).total_seconds()) > self.clock_skew_seconds

        self._seen_ids.add(identity)
        if self._latest_event_time is None or event.event_time > self._latest_event_time:
            self._latest_event_time = event.event_time
        if reordered:
            self.counters[DecisionReason.REORDERED] += 1
        if skew:
            self.counters[DecisionReason.CLOCK_SKEW] += 1
        self.counters[DecisionReason.ACCEPTED] += 1
        return QualityDecision(
            accepted=True,
            reason=DecisionReason.ACCEPTED,
            reordered=reordered,
            clock_skew=skew,
        )

    def status(
        self,
        now: datetime,
        *,
        market_open: bool = True,
        transport_ok: bool = True,
    ) -> QualityStatus:
        if not market_open:
            return QualityStatus(QualityState.MARKET_CLOSED, self._age(now), self._latest_event_time)
        if not transport_ok:
            return QualityStatus(QualityState.SOURCE_ERROR, self._age(now), self._latest_event_time)
        age = self._age(now)
        if age is None:
            state = QualityState.STARTING
        elif age > self.stale_after_seconds:
            state = QualityState.STALE
        elif age > self.gap_after_seconds:
            state = QualityState.GAP
        else:
            state = QualityState.HEALTHY
        return QualityStatus(state, age, self._latest_event_time)

    def _age(self, now: datetime) -> float | None:
        if self._latest_event_time is None:
            return None
        return max(0.0, (now - self._latest_event_time).total_seconds())

    def _reject(self, reason: DecisionReason) -> QualityDecision:
        self.counters[reason] += 1
        return QualityDecision(accepted=False, reason=reason)

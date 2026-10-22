from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock

from price_touch.domain import ForecastSnapshot
from price_touch.labeling import TouchLabels


@dataclass(frozen=True)
class SnapshotRecord:
    snapshot: ForecastSnapshot
    label: TouchLabels | None = None


class SnapshotStore:
    """Thread-safe latest/history store with non-blocking latest-value subscriptions."""

    def __init__(self, persistence_path: Path | None = None) -> None:
        self._records: dict[str, SnapshotRecord] = {}
        self._order: list[str] = []
        self._subscribers: set[asyncio.Queue[ForecastSnapshot]] = set()
        self._lock = RLock()
        self.persistence_path = persistence_path

    def publish(self, snapshot: ForecastSnapshot) -> None:
        # Validation has already guaranteed a full rectangular matrix. Persist first,
        # then expose the same immutable model to readers and subscribers.
        if self.persistence_path is not None:
            self._persist_atomically(snapshot)
        with self._lock:
            if snapshot.forecast_id in self._records:
                raise ValueError(f"duplicate forecast_id: {snapshot.forecast_id}")
            self._records[snapshot.forecast_id] = SnapshotRecord(snapshot)
            self._order.append(snapshot.forecast_id)
            subscribers = tuple(self._subscribers)
        for queue in subscribers:
            if queue.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    queue.get_nowait()
            queue.put_nowait(snapshot)

    def latest(self) -> ForecastSnapshot | None:
        with self._lock:
            return self._records[self._order[-1]].snapshot if self._order else None

    def list_snapshots(self, *, limit: int | None = None) -> list[ForecastSnapshot]:
        with self._lock:
            ids = self._order[-limit:] if limit is not None else self._order
            return [self._records[forecast_id].snapshot for forecast_id in ids]

    def records(self) -> list[SnapshotRecord]:
        with self._lock:
            return [self._records[forecast_id] for forecast_id in self._order]

    def get_record(self, forecast_id: str) -> SnapshotRecord:
        with self._lock:
            try:
                return self._records[forecast_id]
            except KeyError as error:
                raise KeyError(f"unknown forecast_id: {forecast_id}") from error

    def attach_label(self, forecast_id: str, label: TouchLabels) -> None:
        with self._lock:
            record = self.get_record(forecast_id)
            self._records[forecast_id] = replace(record, label=label)

    def subscribe(self) -> asyncio.Queue[ForecastSnapshot]:
        queue: asyncio.Queue[ForecastSnapshot] = asyncio.Queue(maxsize=1)
        latest = self.latest()
        if latest is not None:
            queue.put_nowait(latest)
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ForecastSnapshot]) -> None:
        with self._lock:
            self._subscribers.discard(queue)

    def _persist_atomically(self, snapshot: ForecastSnapshot) -> None:
        assert self.persistence_path is not None
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(
            dir=self.persistence_path.parent,
            prefix=f".{self.persistence_path.name}.",
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(snapshot.model_dump_json())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.persistence_path)
        except BaseException:
            Path(temporary).unlink(missing_ok=True)
            raise

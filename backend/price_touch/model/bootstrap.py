from __future__ import annotations

import hashlib
import math

import numpy as np

from price_touch.domain import ForecastGeometry
from price_touch.model.analytic import NANOSECONDS_PER_SECOND, AnalyticModel
from price_touch.model.features import FeatureState
from price_touch.model.types import ProbabilityMatrix


def paths_to_touch_probabilities(
    paths: np.ndarray,
    geometry: ForecastGeometry,
    *,
    step_seconds: int,
) -> np.ndarray:
    if paths.ndim != 2:
        raise ValueError("paths must have shape (path_count, step_count)")
    if step_seconds <= 0:
        raise ValueError("step_seconds must be positive")
    path_count, step_count = paths.shape
    if path_count == 0:
        raise ValueError("at least one path is required")
    event_times = geometry.origin_ns + np.arange(1, step_count + 1) * step_seconds * NANOSECONDS_PER_SECOND
    probabilities = np.zeros((len(geometry.intervals), len(geometry.windows)), dtype=float)

    for column, window in enumerate(geometry.windows):
        time_mask = (event_times >= window.start_ns) & (event_times < window.end_ns)
        segment = paths[:, time_mask]
        if segment.shape[1] == 0:
            continue
        for row, interval in enumerate(geometry.intervals):
            hits = ((segment >= interval.lower_ticks) & (segment < interval.upper_ticks)).any(axis=1)
            probabilities[row, column] = float(hits.mean())
    return probabilities


class BootstrapModel:
    def __init__(self, *, block_size: int = 5, step_seconds: int = 1) -> None:
        if block_size < 1 or step_seconds < 1:
            raise ValueError("block_size and step_seconds must be positive")
        self.block_size = block_size
        self.step_seconds = step_seconds

    def predict(
        self,
        geometry: ForecastGeometry,
        state: FeatureState,
        *,
        forecast_id: str,
        path_count: int,
    ) -> ProbabilityMatrix:
        if path_count < 1:
            raise ValueError("path_count must be positive")
        if not state.returns:
            return AnalyticModel().predict(geometry, state)

        horizon_seconds = math.ceil(
            (geometry.windows[-1].end_ns - geometry.origin_ns) / NANOSECONDS_PER_SECOND
        )
        step_count = math.ceil(horizon_seconds / self.step_seconds)
        seed = int.from_bytes(hashlib.blake2b(forecast_id.encode(), digest_size=8).digest(), "big")
        rng = np.random.default_rng(seed)
        pool = np.asarray(state.returns, dtype=float)
        block_count = math.ceil(step_count / self.block_size)
        starts = rng.integers(0, len(pool), size=(path_count, block_count, 1))
        offsets = np.arange(self.block_size).reshape(1, 1, -1)
        sampled_indices = (starts + offsets) % len(pool)
        sampled_returns = pool[sampled_indices].reshape(path_count, -1)[:, :step_count]
        paths = geometry.origin_price_ticks * np.exp(np.cumsum(sampled_returns, axis=1))
        probabilities = paths_to_touch_probabilities(paths, geometry, step_seconds=self.step_seconds)
        return ProbabilityMatrix(
            values=np.clip(probabilities, 0, 1),
            method="REGIME_BLOCK_BOOTSTRAP",
            path_count=path_count,
            simulation_batches=1,
        )

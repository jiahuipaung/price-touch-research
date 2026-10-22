from __future__ import annotations

import json
import statistics
import time

from price_touch.config import MatrixConfig
from price_touch.geometry import build_geometry
from price_touch.model.bootstrap import BootstrapModel
from price_touch.model.features import FeatureState


def main() -> None:
    geometry = build_geometry(0, 10_000_000, 10_000, MatrixConfig())
    returns = tuple(((-1) ** index) * (0.0002 + (index % 5) * 0.00005) for index in range(240))
    state = FeatureState(
        cutoff_ns=0,
        latest_price_ticks=10_000_000,
        returns=returns,
        robust_drift=0,
        robust_scale=0.0003,
        max_abs_return=0.0004,
        sample_count=len(returns),
        sufficient=True,
    )
    durations: list[float] = []
    model = BootstrapModel(block_size=5)
    for run in range(7):
        started = time.perf_counter()
        result = model.predict(geometry, state, forecast_id=f"benchmark-{run}", path_count=2_000)
        durations.append((time.perf_counter() - started) * 1000)
    ordered = sorted(durations)
    p95_index = min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))
    print(
        json.dumps(
            {
                "cells": result.values.size,
                "path_count": result.path_count,
                "runs": len(durations),
                "p50_ms": round(statistics.median(durations), 3),
                "p95_ms": round(ordered[p95_index], 3),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

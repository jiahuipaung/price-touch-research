from __future__ import annotations

import math

import numpy as np

from price_touch.domain import ForecastGeometry
from price_touch.model.features import FeatureState
from price_touch.model.types import ProbabilityMatrix

NANOSECONDS_PER_SECOND = 1_000_000_000


def _normal_cdf(value: float) -> float:
    return 0.5 * (1 + math.erf(value / math.sqrt(2)))


class AnalyticModel:
    def predict(self, geometry: ForecastGeometry, state: FeatureState) -> ProbabilityMatrix:
        rows = len(geometry.intervals)
        columns = len(geometry.windows)
        values = np.zeros((rows, columns), dtype=float)
        origin = float(geometry.origin_price_ticks)

        for column, window in enumerate(geometry.windows):
            start_second = max(1, math.ceil((window.start_ns - geometry.origin_ns) / NANOSECONDS_PER_SECOND))
            end_second = math.ceil((window.end_ns - geometry.origin_ns) / NANOSECONDS_PER_SECOND)
            sample_times = range(start_second, end_second)
            for row, interval in enumerate(geometry.intervals):
                not_touched = 1.0
                for second in sample_times:
                    if state.robust_scale <= 1e-12:
                        price = origin * math.exp(state.robust_drift * second)
                        inside_probability = float(interval.lower_ticks <= price < interval.upper_ticks)
                    elif interval.upper_ticks <= 0:
                        inside_probability = 0.0
                    else:
                        sigma = state.robust_scale * math.sqrt(second)
                        mean = math.log(origin) + state.robust_drift * second
                        lower = max(interval.lower_ticks, 1e-12)
                        low_z = (math.log(lower) - mean) / sigma
                        high_z = (math.log(interval.upper_ticks) - mean) / sigma
                        inside_probability = max(0.0, min(1.0, _normal_cdf(high_z) - _normal_cdf(low_z)))
                    not_touched *= 1 - inside_probability
                values[row, column] = 1 - not_touched

        return ProbabilityMatrix(values=np.clip(values, 0, 1), method="ANALYTIC_DIFFUSION")

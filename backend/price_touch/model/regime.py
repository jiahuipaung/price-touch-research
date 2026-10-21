from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum

import numpy as np

from price_touch.model.features import FeatureState


class Regime(StrEnum):
    INSUFFICIENT = "INSUFFICIENT"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    SHOCK = "SHOCK"


def classify_regime(state: FeatureState, historical_volatilities: Sequence[float]) -> Regime:
    if not state.sufficient:
        return Regime.INSUFFICIENT
    history = np.asarray([value for value in historical_volatilities if np.isfinite(value) and value >= 0])
    reference_scale = float(np.median(history)) if history.size else state.robust_scale
    shock_threshold = max(0.02, 8 * reference_scale)
    if state.max_abs_return >= shock_threshold:
        return Regime.SHOCK
    if history.size == 0:
        return Regime.MEDIUM
    low_threshold, high_threshold = np.quantile(history, [1 / 3, 2 / 3])
    if state.robust_scale <= low_threshold:
        return Regime.LOW
    if state.robust_scale >= high_threshold:
        return Regime.HIGH
    return Regime.MEDIUM

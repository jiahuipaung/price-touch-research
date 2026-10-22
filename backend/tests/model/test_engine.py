from __future__ import annotations

import numpy as np
from price_touch.config import MatrixConfig
from price_touch.domain import QualityFlag
from price_touch.geometry import build_geometry
from price_touch.model.engine import ProbabilityEngine
from price_touch.model.features import FeatureState
from price_touch.model.types import ProbabilityMatrix


def geometry():
    return build_geometry(0, 100_000, 200, MatrixConfig(interval_count=3, window_count=1))


def feature_state() -> FeatureState:
    return FeatureState(
        cutoff_ns=0,
        latest_price_ticks=100_000,
        returns=(-0.001, 0.001, -0.0005, 0.0005),
        robust_drift=0,
        robust_scale=0.001,
        max_abs_return=0.001,
        sample_count=4,
        sufficient=True,
    )


class TimeoutThenSuccess:
    def __init__(self) -> None:
        self.path_counts: list[int] = []

    def predict(self, geometry, state, *, forecast_id: str, path_count: int) -> ProbabilityMatrix:
        self.path_counts.append(path_count)
        if path_count > 100:
            raise TimeoutError("budget exhausted")
        return ProbabilityMatrix(
            values=np.full((len(geometry.intervals), len(geometry.windows)), 0.4),
            method="TEST_BOOTSTRAP",
            path_count=path_count,
            simulation_batches=1,
        )


class AlwaysTimeout:
    def predict(self, geometry, state, *, forecast_id: str, path_count: int) -> ProbabilityMatrix:
        raise TimeoutError("still too slow")


class InvalidPrimary:
    def predict(self, geometry, state, *, forecast_id: str, path_count: int) -> ProbabilityMatrix:
        return ProbabilityMatrix(
            values=np.full((len(geometry.intervals), len(geometry.windows)), np.nan),
            method="BROKEN",
            path_count=path_count,
        )


def test_timeout_reduces_paths_before_returning_a_fresh_result() -> None:
    primary = TimeoutThenSuccess()
    engine = ProbabilityEngine(primary=primary, primary_path_count=1_000, reduced_path_count=100)

    result = engine.forecast(geometry(), feature_state(), forecast_id="one")

    assert result is not None
    assert primary.path_counts == [1_000, 100]
    assert result.path_count == 100
    assert QualityFlag.REDUCED_PATHS in result.quality_flags
    assert np.isfinite(result.calibrated.values).all()


def test_repeated_timeout_falls_back_to_visible_analytic_result() -> None:
    engine = ProbabilityEngine(primary=AlwaysTimeout(), primary_path_count=1_000, reduced_path_count=100)

    result = engine.forecast(geometry(), feature_state(), forecast_id="two")

    assert result is not None
    assert result.raw.method == "ANALYTIC_DIFFUSION"
    assert QualityFlag.ANALYTIC_FALLBACK in result.quality_flags
    assert QualityFlag.UNCALIBRATED in result.quality_flags


def test_nonfinite_primary_output_produces_no_fresh_result() -> None:
    engine = ProbabilityEngine(primary=InvalidPrimary(), primary_path_count=1_000, reduced_path_count=100)

    assert engine.forecast(geometry(), feature_state(), forecast_id="broken") is None

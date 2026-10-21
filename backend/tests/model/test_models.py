from __future__ import annotations

import numpy as np
from price_touch.config import MatrixConfig
from price_touch.geometry import build_geometry
from price_touch.model.analytic import AnalyticModel
from price_touch.model.bootstrap import BootstrapModel, paths_to_touch_probabilities
from price_touch.model.features import FeatureState


def geometry(intervals: int = 5, windows: int = 2):
    return build_geometry(
        origin_ns=0,
        origin_price_ticks=100_000,
        step_ticks=200,
        config=MatrixConfig(interval_count=intervals, window_count=windows),
    )


def state(scale: float, returns: tuple[float, ...]) -> FeatureState:
    return FeatureState(
        cutoff_ns=0,
        latest_price_ticks=100_000,
        returns=returns,
        robust_drift=0.0,
        robust_scale=scale,
        max_abs_return=max((abs(value) for value in returns), default=0.0),
        sample_count=len(returns),
        sufficient=len(returns) >= 2,
    )


def assert_probability_matrix(values: np.ndarray, rows: int = 5, columns: int = 2) -> None:
    assert values.shape == (rows, columns)
    assert np.isfinite(values).all()
    assert ((values >= 0) & (values <= 1)).all()


def test_analytic_model_returns_complete_finite_matrix() -> None:
    result = AnalyticModel().predict(
        geometry(),
        state(0.001, (-0.001, 0.001, -0.0005, 0.0005)),
    )

    assert_probability_matrix(result.values)
    assert result.method == "ANALYTIC_DIFFUSION"


def test_higher_volatility_increases_near_term_probability_for_a_distant_interval() -> None:
    model = AnalyticModel()
    low = model.predict(geometry(), state(0.0001, (-0.0001, 0.0001))).values
    high = model.predict(geometry(), state(0.01, (-0.01, 0.01))).values

    assert high[-1, 0] > low[-1, 0]


def test_bootstrap_is_deterministic_for_forecast_id_and_uses_one_path_batch() -> None:
    model = BootstrapModel(block_size=2)
    feature_state = state(0.001, (-0.001, 0.002, -0.0005, 0.0015, -0.002, 0.0007))

    first = model.predict(geometry(), feature_state, forecast_id="forecast-42", path_count=256)
    second = model.predict(geometry(), feature_state, forecast_id="forecast-42", path_count=256)

    assert_probability_matrix(first.values)
    assert np.array_equal(first.values, second.values)
    assert first.simulation_batches == 1
    assert first.path_count == 256


def test_discrete_jump_does_not_mark_the_skipped_center_interval() -> None:
    small_geometry = build_geometry(
        origin_ns=0,
        origin_price_ticks=1_000,
        step_ticks=200,
        config=MatrixConfig(interval_count=3, window_count=1),
    )
    paths = np.asarray([[850, 850, 850, 850, 850, 1_150, 1_150, 1_150, 1_150, 1_150]], dtype=float)

    probabilities = paths_to_touch_probabilities(paths, small_geometry, step_seconds=1)

    assert probabilities[:, 0].tolist() == [1.0, 0.0, 1.0]

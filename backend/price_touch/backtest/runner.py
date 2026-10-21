from __future__ import annotations

from dataclasses import dataclass, field

from price_touch.config import MatrixConfig
from price_touch.domain import ForecastGeometry, MarketEvent
from price_touch.geometry import NANOSECONDS_PER_SECOND, build_geometry
from price_touch.labeling import LabelPrecision, TouchLabels, label_forecast
from price_touch.model.calibration import CalibrationRow, fit_calibrator
from price_touch.model.engine import ModelResult, ProbabilityEngine
from price_touch.model.features import FeatureState, compute_features, event_time_ns
from price_touch.model.regime import Regime, classify_regime


@dataclass(frozen=True)
class BacktestConfig:
    asset: str
    instrument: str
    step_ticks: int
    matrix: MatrixConfig
    origin_cadence_seconds: int = 5
    warmup_seconds: int = 30
    label_precision: LabelPrecision = LabelPrecision.TICK_EXACT


@dataclass
class BacktestForecast:
    forecast_id: str
    origin_ns: int
    matures_at_ns: int
    geometry: ForecastGeometry
    feature_state: FeatureState
    regime: Regime
    result: ModelResult
    calibration_sample_count: int
    labels: TouchLabels | None = None


@dataclass
class BacktestRun:
    config: BacktestConfig
    forecasts: list[BacktestForecast] = field(default_factory=list)


class WalkForwardRunner:
    def __init__(self, engine: ProbabilityEngine, config: BacktestConfig) -> None:
        self.engine = engine
        self.config = config

    def run(self, events: list[MarketEvent]) -> BacktestRun:
        ordered = sorted(events, key=lambda event: (event.event_time, event.trade_id))
        if not ordered:
            return BacktestRun(self.config)
        first_ns = event_time_ns(ordered[0])
        last_ns = event_time_ns(ordered[-1])
        cadence_ns = self.config.origin_cadence_seconds * NANOSECONDS_PER_SECOND
        first_origin = first_ns + self.config.warmup_seconds * NANOSECONDS_PER_SECOND
        run = BacktestRun(self.config)
        calibration_rows: list[CalibrationRow] = []
        prior_feature_scales: list[float] = []

        for origin_ns in range(first_origin, last_ns + 1, cadence_ns):
            self._mature_forecasts(run.forecasts, ordered, origin_ns, calibration_rows)
            state = compute_features(ordered, cutoff_ns=origin_ns)
            if state.latest_price_ticks is None:
                continue
            regime = classify_regime(state, prior_feature_scales)
            calibrator = fit_calibrator(calibration_rows, cutoff_ns=origin_ns)
            geometry = build_geometry(
                origin_ns,
                state.latest_price_ticks,
                self.config.step_ticks,
                self.config.matrix,
            )
            forecast_id = f"{self.config.asset}:{origin_ns}"
            result = self.engine.forecast(
                geometry,
                state,
                forecast_id=forecast_id,
                calibrator=calibrator,
            )
            if result is None:
                prior_feature_scales.append(state.robust_scale)
                continue
            run.forecasts.append(
                BacktestForecast(
                    forecast_id=forecast_id,
                    origin_ns=origin_ns,
                    matures_at_ns=geometry.windows[-1].end_ns,
                    geometry=geometry,
                    feature_state=state,
                    regime=regime,
                    result=result,
                    calibration_sample_count=calibrator.sample_count,
                )
            )
            prior_feature_scales.append(state.robust_scale)

        self._mature_forecasts(run.forecasts, ordered, last_ns, calibration_rows)
        return run

    def _mature_forecasts(
        self,
        forecasts: list[BacktestForecast],
        events: list[MarketEvent],
        available_through_ns: int,
        calibration_rows: list[CalibrationRow],
    ) -> None:
        for forecast in forecasts:
            if forecast.labels is not None or forecast.matures_at_ns > available_through_ns:
                continue
            forecast.labels = label_forecast(forecast.geometry, events, self.config.label_precision)
            for row_index, row in enumerate(forecast.labels.values):
                for column_index, label in enumerate(row):
                    calibration_rows.append(
                        CalibrationRow(
                            probability=float(forecast.result.raw.values[row_index, column_index]),
                            label=label,
                            matured_at_ns=forecast.matures_at_ns,
                        )
                    )

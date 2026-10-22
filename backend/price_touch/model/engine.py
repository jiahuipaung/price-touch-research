from __future__ import annotations

from dataclasses import dataclass

from price_touch.domain import ForecastGeometry, QualityFlag
from price_touch.model.analytic import AnalyticModel
from price_touch.model.bootstrap import BootstrapModel
from price_touch.model.calibration import CalibrationArtifact
from price_touch.model.features import FeatureState
from price_touch.model.types import ProbabilityMatrix


@dataclass(frozen=True)
class ModelResult:
    baseline: ProbabilityMatrix
    raw: ProbabilityMatrix
    calibrated: ProbabilityMatrix
    quality_flags: list[QualityFlag]
    path_count: int


class ProbabilityEngine:
    def __init__(
        self,
        *,
        analytic: AnalyticModel | None = None,
        primary: BootstrapModel | None = None,
        primary_path_count: int = 2_000,
        reduced_path_count: int = 500,
    ) -> None:
        if not 0 < reduced_path_count <= primary_path_count:
            raise ValueError("path counts must satisfy 0 < reduced <= primary")
        self.analytic = analytic or AnalyticModel()
        self.primary = primary or BootstrapModel()
        self.primary_path_count = primary_path_count
        self.reduced_path_count = reduced_path_count

    def forecast(
        self,
        geometry: ForecastGeometry,
        state: FeatureState,
        *,
        forecast_id: str,
        calibrator: CalibrationArtifact | None = None,
    ) -> ModelResult | None:
        baseline = self.analytic.predict(geometry, state)
        flags: list[QualityFlag] = []
        try:
            raw = self.primary.predict(
                geometry,
                state,
                forecast_id=forecast_id,
                path_count=self.primary_path_count,
            )
        except TimeoutError:
            flags.append(QualityFlag.REDUCED_PATHS)
            try:
                raw = self.primary.predict(
                    geometry,
                    state,
                    forecast_id=forecast_id,
                    path_count=self.reduced_path_count,
                )
            except TimeoutError:
                raw = baseline
                flags.append(QualityFlag.ANALYTIC_FALLBACK)

        if not baseline.is_valid() or not raw.is_valid() or raw.values.shape != baseline.values.shape:
            return None

        calibration = calibrator or CalibrationArtifact.uncalibrated(state.cutoff_ns)
        calibrated_values = calibration.apply_many(raw.values)
        calibrated = ProbabilityMatrix(
            values=calibrated_values,
            method=f"CALIBRATED_{calibration.method}",
            path_count=raw.path_count,
            simulation_batches=raw.simulation_batches,
        )
        if not calibrated.is_valid():
            return None
        flags.extend(flag for flag in calibration.quality_flags if flag not in flags)
        return ModelResult(
            baseline=baseline,
            raw=raw,
            calibrated=calibrated,
            quality_flags=flags,
            path_count=raw.path_count,
        )

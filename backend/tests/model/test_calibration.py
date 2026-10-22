from __future__ import annotations

import numpy as np
from price_touch.domain import QualityFlag
from price_touch.model.calibration import CalibrationRow, fit_calibrator


def test_isotonic_calibrator_uses_only_matured_rows_before_cutoff_and_is_monotone() -> None:
    rows = [
        CalibrationRow(
            probability=index / 59,
            label=int(index >= 30),
            matured_at_ns=index,
        )
        for index in range(60)
    ]
    rows.append(CalibrationRow(probability=0.99, label=0, matured_at_ns=10_000))

    artifact = fit_calibrator(rows, cutoff_ns=100, min_isotonic_samples=50, min_shrinkage_samples=5)

    assert artifact.method == "ISOTONIC"
    assert artifact.sample_count == 60
    assert artifact.max_matured_at_ns == 59
    calibrated = artifact.apply_many(np.asarray([0.1, 0.4, 0.6, 0.9]))
    assert np.isfinite(calibrated).all()
    assert ((calibrated >= 0) & (calibrated <= 1)).all()
    assert np.diff(calibrated).min() >= 0


def test_sparse_rows_use_monotone_shrinkage_mapping() -> None:
    rows = [
        CalibrationRow(probability=probability, label=label, matured_at_ns=index)
        for index, (probability, label) in enumerate(
            [(0.1, 0), (0.2, 0), (0.4, 1), (0.6, 0), (0.8, 1), (0.9, 1)]
        )
    ]

    artifact = fit_calibrator(rows, cutoff_ns=100, min_isotonic_samples=50, min_shrinkage_samples=5)

    assert artifact.method == "SHRINKAGE"
    assert artifact.quality_flags == []
    assert artifact.apply(0.2) < artifact.apply(0.8)


def test_too_few_rows_leave_probability_unchanged_and_flag_uncalibrated() -> None:
    artifact = fit_calibrator(
        [CalibrationRow(probability=0.3, label=1, matured_at_ns=1)],
        cutoff_ns=100,
        min_isotonic_samples=50,
        min_shrinkage_samples=5,
    )

    assert artifact.method == "UNCALIBRATED"
    assert artifact.apply(0.3) == 0.3
    assert artifact.quality_flags == [QualityFlag.UNCALIBRATED]

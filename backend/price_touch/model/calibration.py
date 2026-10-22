from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

from price_touch.domain import QualityFlag


@dataclass(frozen=True)
class CalibrationRow:
    probability: float
    label: int
    matured_at_ns: int


@dataclass(frozen=True)
class CalibrationArtifact:
    method: str
    sample_count: int
    cutoff_ns: int
    max_matured_at_ns: int | None
    x: tuple[float, ...]
    y: tuple[float, ...]
    quality_flags: list[QualityFlag]

    @classmethod
    def uncalibrated(cls, cutoff_ns: int = 0, sample_count: int = 0) -> CalibrationArtifact:
        return cls(
            method="UNCALIBRATED",
            sample_count=sample_count,
            cutoff_ns=cutoff_ns,
            max_matured_at_ns=None,
            x=(),
            y=(),
            quality_flags=[QualityFlag.UNCALIBRATED],
        )

    def apply(self, probability: float) -> float:
        if not np.isfinite(probability):
            return float("nan")
        value = float(probability)
        if self.method == "UNCALIBRATED" or not self.x:
            return float(np.clip(value, 0, 1))
        return float(np.clip(np.interp(value, self.x, self.y), 0, 1))

    def apply_many(self, probabilities: np.ndarray) -> np.ndarray:
        if self.method == "UNCALIBRATED" or not self.x:
            return np.clip(probabilities.astype(float), 0, 1)
        return np.clip(np.interp(probabilities, self.x, self.y), 0, 1)


def _isotonic_points(
    probabilities: np.ndarray,
    labels: np.ndarray,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    unique_x, inverse, counts = np.unique(probabilities, return_inverse=True, return_counts=True)
    sums = np.zeros_like(unique_x, dtype=float)
    np.add.at(sums, inverse, labels)
    means = sums / counts
    blocks: list[dict[str, float | int]] = []
    for index, (mean, weight) in enumerate(zip(means, counts, strict=True)):
        blocks.append({"start": index, "end": index, "level": float(mean), "weight": int(weight)})
        while len(blocks) >= 2 and float(blocks[-2]["level"]) > float(blocks[-1]["level"]):
            right = blocks.pop()
            left = blocks.pop()
            total_weight = int(left["weight"]) + int(right["weight"])
            level = (
                float(left["level"]) * int(left["weight"])
                + float(right["level"]) * int(right["weight"])
            ) / total_weight
            blocks.append(
                {
                    "start": int(left["start"]),
                    "end": int(right["end"]),
                    "level": level,
                    "weight": total_weight,
                }
            )
    fitted = np.zeros_like(unique_x, dtype=float)
    for block in blocks:
        fitted[int(block["start"]) : int(block["end"]) + 1] = float(block["level"])
    return tuple(float(value) for value in unique_x), tuple(float(value) for value in fitted)


def fit_calibrator(
    matured_rows: Iterable[CalibrationRow],
    *,
    cutoff_ns: int,
    min_isotonic_samples: int = 50,
    min_shrinkage_samples: int = 10,
) -> CalibrationArtifact:
    eligible = [
        row
        for row in matured_rows
        if row.matured_at_ns < cutoff_ns
        and np.isfinite(row.probability)
        and 0 <= row.probability <= 1
        and row.label in (0, 1)
    ]
    if len(eligible) < min_shrinkage_samples:
        artifact = CalibrationArtifact.uncalibrated(cutoff_ns=cutoff_ns, sample_count=len(eligible))
        return CalibrationArtifact(
            **{
                **artifact.__dict__,
                "max_matured_at_ns": max((row.matured_at_ns for row in eligible), default=None),
            }
        )

    max_matured = max(row.matured_at_ns for row in eligible)
    probabilities = np.asarray([row.probability for row in eligible], dtype=float)
    labels = np.asarray([row.label for row in eligible], dtype=float)
    if len(eligible) >= min_isotonic_samples:
        x, y = _isotonic_points(probabilities, labels)
        method = "ISOTONIC"
    else:
        posterior_rate = float((labels.sum() + 1) / (len(labels) + 2))
        x = (0.0, 1.0)
        y = (0.5 * posterior_rate, 0.5 + 0.5 * posterior_rate)
        method = "SHRINKAGE"
    return CalibrationArtifact(
        method=method,
        sample_count=len(eligible),
        cutoff_ns=cutoff_ns,
        max_matured_at_ns=max_matured,
        x=x,
        y=y,
        quality_flags=[],
    )

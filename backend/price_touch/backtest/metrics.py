from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MetricRow:
    forecast_id: str
    probability: float | None
    baseline_probability: float | None
    label: int | None
    asset: str
    regime: str
    horizon_bucket: str
    distance_bucket: str
    label_precision: str


@dataclass(frozen=True)
class ReliabilityBin:
    lower: float
    upper: float
    count: int
    mean_probability: float
    observed_frequency: float


@dataclass(frozen=True)
class MetricSummary:
    count: int
    skipped: int
    coverage: float
    brier_score: float
    baseline_brier: float
    brier_skill: float
    log_loss: float
    ece: float
    calibration_intercept: float
    calibration_slope: float
    brier_ci: tuple[float, float]


@dataclass(frozen=True)
class MetricReport:
    overall: MetricSummary
    reliability: list[ReliabilityBin]
    groups: dict[str, MetricSummary]


def _eligible(rows: list[MetricRow]) -> list[MetricRow]:
    return [
        row
        for row in rows
        if row.probability is not None
        and row.baseline_probability is not None
        and row.label in (0, 1)
        and math.isfinite(row.probability)
        and math.isfinite(row.baseline_probability)
    ]


def _calibration_coefficients(probabilities: np.ndarray, labels: np.ndarray) -> tuple[float, float]:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    design = np.column_stack([np.ones_like(logits), logits])
    beta = np.zeros(2, dtype=float)
    for _ in range(30):
        linear = np.clip(design @ beta, -30, 30)
        fitted = 1 / (1 + np.exp(-linear))
        weights = np.maximum(fitted * (1 - fitted), 1e-8)
        hessian = design.T @ (weights[:, None] * design) + np.eye(2) * 1e-8
        gradient = design.T @ (labels - fitted)
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.linalg.norm(step) < 1e-8:
            break
    return float(beta[0]), float(beta[1])


def _brier_interval(
    errors: np.ndarray,
    *,
    block_size: int,
    seed: int,
    samples: int,
) -> tuple[float, float]:
    observed = float(errors.mean())
    if len(errors) < 2 or samples <= 0:
        return observed, observed
    rng = np.random.default_rng(seed)
    estimates = []
    block_count = math.ceil(len(errors) / block_size)
    offsets = np.arange(block_size)
    for _ in range(samples):
        starts = rng.integers(0, len(errors), size=block_count)
        indices = ((starts[:, None] + offsets) % len(errors)).reshape(-1)[: len(errors)]
        estimates.append(float(errors[indices].mean()))
    lower, upper = np.quantile(estimates, [0.025, 0.975])
    return min(float(lower), observed), max(float(upper), observed)


def _summary(
    all_rows: list[MetricRow],
    valid: list[MetricRow],
    *,
    bin_count: int,
    block_size: int,
    seed: int,
    bootstrap_samples: int,
) -> MetricSummary:
    skipped = len(all_rows) - len(valid)
    coverage = len(valid) / len(all_rows) if all_rows else 0.0
    if not valid:
        nan = float("nan")
        return MetricSummary(0, skipped, coverage, nan, nan, nan, nan, nan, nan, nan, (nan, nan))
    probabilities = np.asarray([row.probability for row in valid], dtype=float)
    baseline = np.asarray([row.baseline_probability for row in valid], dtype=float)
    labels = np.asarray([row.label for row in valid], dtype=float)
    errors = (probabilities - labels) ** 2
    baseline_errors = (baseline - labels) ** 2
    brier = float(errors.mean())
    baseline_brier = float(baseline_errors.mean())
    skill = 1 - brier / baseline_brier if baseline_brier > 0 else float("nan")
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    log_loss = float(-(labels * np.log(clipped) + (1 - labels) * np.log(1 - clipped)).mean())
    reliability = _reliability(valid, bin_count)
    ece = sum(
        item.count / len(valid) * abs(item.mean_probability - item.observed_frequency) for item in reliability
    )
    intercept, slope = _calibration_coefficients(probabilities, labels)
    return MetricSummary(
        count=len(valid),
        skipped=skipped,
        coverage=coverage,
        brier_score=brier,
        baseline_brier=baseline_brier,
        brier_skill=skill,
        log_loss=log_loss,
        ece=float(ece),
        calibration_intercept=intercept,
        calibration_slope=slope,
        brier_ci=_brier_interval(
            errors,
            block_size=block_size,
            seed=seed,
            samples=bootstrap_samples,
        ),
    )


def _reliability(rows: list[MetricRow], bin_count: int) -> list[ReliabilityBin]:
    bins: list[list[MetricRow]] = [[] for _ in range(bin_count)]
    for row in rows:
        assert row.probability is not None
        index = min(int(row.probability * bin_count), bin_count - 1)
        bins[index].append(row)
    result = []
    for index, bucket in enumerate(bins):
        if not bucket:
            continue
        result.append(
            ReliabilityBin(
                lower=index / bin_count,
                upper=(index + 1) / bin_count,
                count=len(bucket),
                mean_probability=float(np.mean([row.probability for row in bucket])),
                observed_frequency=float(np.mean([row.label for row in bucket])),
            )
        )
    return result


def compute_metrics(
    rows: list[MetricRow],
    *,
    bin_count: int = 10,
    block_size: int = 12,
    seed: int = 0,
    bootstrap_samples: int = 200,
) -> MetricReport:
    if bin_count < 1 or block_size < 1:
        raise ValueError("bin_count and block_size must be positive")
    valid = _eligible(rows)
    overall = _summary(
        rows,
        valid,
        bin_count=bin_count,
        block_size=block_size,
        seed=seed,
        bootstrap_samples=bootstrap_samples,
    )
    dimensions = {
        "asset": "asset",
        "regime": "regime",
        "horizon": "horizon_bucket",
        "distance": "distance_bucket",
        "label_precision": "label_precision",
    }
    groups: dict[str, MetricSummary] = {}
    for prefix, attribute in dimensions.items():
        values = sorted({getattr(row, attribute) for row in rows})
        for value in values:
            subset = [row for row in rows if getattr(row, attribute) == value]
            groups[f"{prefix}:{value}"] = _summary(
                subset,
                _eligible(subset),
                bin_count=bin_count,
                block_size=block_size,
                seed=seed,
                bootstrap_samples=bootstrap_samples,
            )
    return MetricReport(overall=overall, reliability=_reliability(valid, bin_count), groups=groups)

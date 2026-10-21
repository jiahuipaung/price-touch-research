from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

REQUIRED_REGIMES = ("LOW", "MEDIUM", "HIGH", "SHOCK")


@dataclass(frozen=True)
class CoverageManifest:
    evaluation_kind: str
    required_start_ns: int
    required_end_ns: int
    coarse_start_ns: int
    coarse_end_ns: int
    high_resolution_start_ns: int
    high_resolution_end_ns: int
    checksum_verified: bool
    minimum_samples_per_regime: int


@dataclass(frozen=True)
class CoverageRow:
    regime: str
    event_ns: int
    label_precision: str


@dataclass(frozen=True)
class CoverageReport:
    valid: bool
    is_full_cycle: bool
    disclosure: str
    regime_counts: dict[str, int]
    missing_requirements: list[str]


def validate_cycle_coverage(
    manifest: CoverageManifest,
    rows: list[CoverageRow],
) -> CoverageReport:
    counts = Counter(row.regime for row in rows)
    regime_counts = {regime: counts[regime] for regime in REQUIRED_REGIMES}
    if manifest.evaluation_kind == "COMPACT_DEMO":
        missing = [] if manifest.checksum_verified else ["CHECKSUM"]
        return CoverageReport(
            valid=not missing,
            is_full_cycle=False,
            disclosure="COMPACT_DEMO_NOT_FULL_CYCLE",
            regime_counts=regime_counts,
            missing_requirements=missing,
        )

    missing: list[str] = []
    if not manifest.checksum_verified:
        missing.append("CHECKSUM")
    coarse_range_incomplete = (
        manifest.coarse_start_ns > manifest.required_start_ns
        or manifest.coarse_end_ns < manifest.required_end_ns
    )
    if coarse_range_incomplete:
        missing.append("COARSE_TIME_RANGE")
    if (
        manifest.high_resolution_start_ns > manifest.required_start_ns
        or manifest.high_resolution_end_ns < manifest.required_end_ns
    ):
        missing.append("HIGH_RESOLUTION_TIME_RANGE")
    for regime in REQUIRED_REGIMES:
        if counts[regime] < manifest.minimum_samples_per_regime:
            missing.append(f"REGIME_{regime}")
    return CoverageReport(
        valid=not missing,
        is_full_cycle=True,
        disclosure="FULL_CYCLE" if not missing else "FULL_CYCLE_REQUIREMENTS_MISSING",
        regime_counts=regime_counts,
        missing_requirements=missing,
    )

from __future__ import annotations

from dataclasses import replace

import pytest
from price_touch.backtest.coverage import (
    CoverageManifest,
    CoverageRow,
    validate_cycle_coverage,
)


def manifest(**overrides) -> CoverageManifest:
    base = CoverageManifest(
        evaluation_kind="FULL_CYCLE",
        required_start_ns=100,
        required_end_ns=1_000,
        coarse_start_ns=100,
        coarse_end_ns=1_000,
        high_resolution_start_ns=100,
        high_resolution_end_ns=1_000,
        checksum_verified=True,
        minimum_samples_per_regime=2,
    )
    return replace(base, **overrides)


def rows() -> list[CoverageRow]:
    return [
        CoverageRow(regime=regime, event_ns=event_ns, label_precision="TICK_EXACT")
        for regime_index, regime in enumerate(("LOW", "MEDIUM", "HIGH", "SHOCK"))
        for event_ns in (100 + regime_index * 100, 101 + regime_index * 100)
    ]


def test_full_cycle_requires_all_regimes_exact_time_coverage_checksum_and_samples() -> None:
    report = validate_cycle_coverage(manifest(), rows())

    assert report.valid is True
    assert report.is_full_cycle is True
    assert report.missing_requirements == []
    assert report.regime_counts == {"LOW": 2, "MEDIUM": 2, "HIGH": 2, "SHOCK": 2}


@pytest.mark.parametrize(
    ("changed_manifest", "changed_rows", "missing_code"),
    [
        (manifest(), [row for row in rows() if row.regime != "SHOCK"], "REGIME_SHOCK"),
        (manifest(high_resolution_start_ns=101), rows(), "HIGH_RESOLUTION_TIME_RANGE"),
        (manifest(coarse_end_ns=999), rows(), "COARSE_TIME_RANGE"),
        (manifest(checksum_verified=False), rows(), "CHECKSUM"),
        (manifest(minimum_samples_per_regime=3), rows(), "REGIME_LOW"),
    ],
)
def test_missing_full_cycle_evidence_fails_validation(
    changed_manifest: CoverageManifest,
    changed_rows: list[CoverageRow],
    missing_code: str,
) -> None:
    report = validate_cycle_coverage(changed_manifest, changed_rows)

    assert report.valid is False
    assert missing_code in report.missing_requirements


def test_demo_report_is_explicitly_compact_not_full_cycle() -> None:
    report = validate_cycle_coverage(
        manifest(evaluation_kind="COMPACT_DEMO", checksum_verified=True),
        rows()[:2],
    )

    assert report.valid is True
    assert report.is_full_cycle is False
    assert report.disclosure == "COMPACT_DEMO_NOT_FULL_CYCLE"

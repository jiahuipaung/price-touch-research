from __future__ import annotations

import math

import duckdb
import pytest
from price_touch.backtest.metrics import MetricRow, compute_metrics
from price_touch.backtest.storage import write_backtest_rows


def rows() -> list[MetricRow]:
    probabilities = [0.1, 0.4, 0.6, 0.9]
    labels = [0, 1, 1, 1]
    return [
        MetricRow(
            forecast_id=f"forecast-{index}",
            probability=probability,
            baseline_probability=0.5,
            label=label,
            asset="BTC" if index < 2 else "GOLD",
            regime="LOW" if index % 2 == 0 else "HIGH",
            horizon_bucket="5-10s" if index < 2 else "10-15s",
            distance_bucket="NEAR" if index % 2 == 0 else "FAR",
            label_precision="TICK_EXACT" if index < 3 else "BAR_APPROX",
        )
        for index, (probability, label) in enumerate(zip(probabilities, labels, strict=True))
    ]


def test_metrics_match_hand_calculated_brier_log_loss_ece_and_baseline_skill() -> None:
    report = compute_metrics(rows(), bin_count=2, block_size=2, seed=17)

    assert report.overall.brier_score == 0.135
    assert report.overall.log_loss == pytest.approx(
        -(math.log(0.9) + math.log(0.4) + math.log(0.6) + math.log(0.9)) / 4
    )
    assert report.overall.ece == 0.25
    assert report.overall.baseline_brier == 0.25
    assert report.overall.brier_skill == pytest.approx(0.46)
    assert report.overall.coverage == 1.0
    assert report.overall.skipped == 0
    assert math.isfinite(report.overall.calibration_intercept)
    assert report.overall.calibration_slope > 0


def test_metrics_report_reliability_bins_and_all_required_group_dimensions() -> None:
    report = compute_metrics(rows(), bin_count=2, block_size=2, seed=17)

    assert [(item.count, item.mean_probability, item.observed_frequency) for item in report.reliability] == [
        (2, 0.25, 0.5),
        (2, 0.75, 1.0),
    ]
    assert set(report.groups) >= {
        "asset:BTC",
        "asset:GOLD",
        "regime:LOW",
        "regime:HIGH",
        "horizon:5-10s",
        "distance:NEAR",
        "label_precision:TICK_EXACT",
        "label_precision:BAR_APPROX",
    }


def test_skipped_rows_reduce_coverage_without_entering_scores() -> None:
    input_rows = rows() + [
        MetricRow(
            forecast_id="skipped",
            probability=None,
            baseline_probability=None,
            label=None,
            asset="BTC",
            regime="LOW",
            horizon_bucket="5-10s",
            distance_bucket="NEAR",
            label_precision="TICK_EXACT",
        )
    ]

    report = compute_metrics(input_rows, bin_count=2, block_size=2, seed=17)

    assert report.overall.coverage == 0.8
    assert report.overall.skipped == 1
    assert report.overall.count == 4


def test_block_bootstrap_confidence_interval_is_seeded_and_contains_brier() -> None:
    first = compute_metrics(rows() * 4, bin_count=2, block_size=2, seed=42, bootstrap_samples=100)
    second = compute_metrics(rows() * 4, bin_count=2, block_size=2, seed=42, bootstrap_samples=100)

    assert first.overall.brier_ci == second.overall.brier_ci
    assert first.overall.brier_ci[0] <= first.overall.brier_score <= first.overall.brier_ci[1]


def test_storage_writes_cell_parquet_and_queryable_duckdb(tmp_path) -> None:
    artifacts = write_backtest_rows(rows(), tmp_path)

    assert artifacts.parquet_path.exists()
    assert artifacts.duckdb_path.exists()
    with duckdb.connect(str(artifacts.duckdb_path), read_only=True) as connection:
        assert connection.execute("select count(*) from cell_results").fetchone()[0] == 4

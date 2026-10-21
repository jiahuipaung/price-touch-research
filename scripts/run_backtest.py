from __future__ import annotations

import argparse
import csv
import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from price_touch.backtest.coverage import CoverageManifest, CoverageRow, validate_cycle_coverage
from price_touch.backtest.metrics import MetricRow, compute_metrics
from price_touch.backtest.runner import BacktestConfig, WalkForwardRunner
from price_touch.backtest.storage import write_backtest_rows
from price_touch.config import MatrixConfig
from price_touch.domain import MarketEvent
from price_touch.market.manifest import DemoManifest
from price_touch.model.engine import ProbabilityEngine


def load_dataset(manifest_path: Path) -> tuple[DemoManifest, list[MarketEvent]]:
    payload = json.loads(manifest_path.read_text())
    manifest = DemoManifest.model_validate(payload)
    data_path = manifest_path.parent / manifest.file
    digest = hashlib.sha256(data_path.read_bytes()).hexdigest()
    if digest != manifest.sha256:
        raise ValueError(f"dataset checksum mismatch: expected {manifest.sha256}, got {digest}")
    with data_path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    if len(rows) != manifest.row_count:
        raise ValueError(f"dataset row count mismatch: expected {manifest.row_count}, got {len(rows)}")
    events = [
        MarketEvent(
            asset=row["asset"],
            instrument=row["instrument"],
            event_time=datetime.fromisoformat(row["event_time"].replace("Z", "+00:00")),
            received_time=datetime.fromisoformat(row["received_time"].replace("Z", "+00:00")),
            price_ticks=int(row["price_ticks"]),
            trade_id=row["trade_id"],
            kind=row["kind"],
        )
        for row in rows
    ]
    return manifest, events


def metric_rows_from_run(run) -> list[MetricRow]:
    rows: list[MetricRow] = []
    for forecast in run.forecasts:
        for row_index, interval in enumerate(forecast.geometry.intervals):
            for column_index, window in enumerate(forecast.geometry.windows):
                label = forecast.labels.values[row_index][column_index] if forecast.labels else None
                start_seconds = (window.start_ns - forecast.origin_ns) // 1_000_000_000
                end_seconds = (window.end_ns - forecast.origin_ns) // 1_000_000_000
                distance = abs(interval.index)
                rows.append(
                    MetricRow(
                        forecast_id=forecast.forecast_id,
                        probability=float(forecast.result.calibrated.values[row_index, column_index]),
                        baseline_probability=float(forecast.result.baseline.values[row_index, column_index]),
                        label=label,
                        asset=run.config.asset,
                        regime=forecast.regime.value,
                        horizon_bucket=f"{start_seconds}-{end_seconds}s",
                        distance_bucket="CENTER" if distance == 0 else "NEAR" if distance <= 2 else "FAR",
                        label_precision=run.config.label_precision.value,
                    )
                )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Run deterministic walk-forward touch-probability backtest")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest, events = load_dataset(args.dataset)
    config = BacktestConfig(
        asset=manifest.asset,
        instrument=manifest.instrument,
        step_ticks=10_000,
        origin_cadence_seconds=1,
        warmup_seconds=1,
        matrix=MatrixConfig(
            interval_count=5,
            window_count=1,
            observation_delay_seconds=1,
            window_seconds=5,
        ),
    )
    run = WalkForwardRunner(
        ProbabilityEngine(primary_path_count=500, reduced_path_count=100),
        config,
    ).run(events)
    metric_rows = metric_rows_from_run(run)
    report = compute_metrics(metric_rows, bin_count=5, block_size=5, seed=42, bootstrap_samples=100)
    artifacts = write_backtest_rows(metric_rows, args.output)

    start_ns = int(manifest.start_time.timestamp() * 1_000_000_000)
    end_ns = int(manifest.end_time.timestamp() * 1_000_000_000)
    coverage_manifest = CoverageManifest(
        evaluation_kind="COMPACT_DEMO",
        required_start_ns=start_ns,
        required_end_ns=end_ns,
        coarse_start_ns=start_ns,
        coarse_end_ns=end_ns,
        high_resolution_start_ns=start_ns,
        high_resolution_end_ns=end_ns,
        checksum_verified=True,
        minimum_samples_per_regime=1,
    )
    coverage_rows = [
        CoverageRow(
            regime=forecast.regime.value,
            event_ns=forecast.origin_ns,
            label_precision=config.label_precision.value,
        )
        for forecast in run.forecasts
        if forecast.labels is not None
    ]
    coverage = validate_cycle_coverage(coverage_manifest, coverage_rows)
    summary = {
        "dataset": manifest.model_dump(mode="json"),
        "forecast_count": len(run.forecasts),
        "matured_forecast_count": sum(forecast.labels is not None for forecast in run.forecasts),
        "metrics": asdict(report.overall),
        "reliability": [asdict(item) for item in report.reliability],
        "groups": {name: asdict(value) for name, value in report.groups.items()},
        "coverage": asdict(coverage),
        "artifacts": {
            "parquet": str(artifacts.parquet_path),
            "duckdb": str(artifacts.duckdb_path),
        },
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=True))
    print(json.dumps(summary, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()

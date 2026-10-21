from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
import polars as pl

from price_touch.backtest.metrics import MetricRow


@dataclass(frozen=True)
class StorageArtifacts:
    parquet_path: Path
    duckdb_path: Path


def write_backtest_rows(rows: list[MetricRow], output_dir: Path) -> StorageArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = output_dir / "cell-results.parquet"
    duckdb_path = output_dir / "research.duckdb"
    pl.DataFrame([asdict(row) for row in rows]).write_parquet(parquet_path)
    with duckdb.connect(str(duckdb_path)) as connection:
        connection.execute(
            "CREATE OR REPLACE TABLE cell_results AS SELECT * FROM read_parquet(?)",
            [str(parquet_path)],
        )
    return StorageArtifacts(parquet_path=parquet_path, duckdb_path=duckdb_path)

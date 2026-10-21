# Acceptance evidence map

## Automated local gate

Run `make verify`. A pass means:

| Requirement | Evidence |
|---|---|
| Half-open price/time geometry and exact/jump labels | `backend/tests/test_geometry.py`, `test_labeling.py` |
| Duplicate, reorder, gap, stale, closure, recovery | `backend/tests/market/` |
| Past-only features, deterministic paths, finite matrices, fallback | `backend/tests/model/` |
| Chronological walk-forward and matured-only calibration | `backend/tests/backtest/test_walk_forward.py` |
| Metrics, reliability, block CI, Parquet/DuckDB | `backend/tests/backtest/test_metrics.py` |
| Full-cycle contract rejects missing regime/range/checksum | `backend/tests/backtest/test_coverage.py` |
| Atomic snapshots, non-blocking clients, no stale re-ID | `backend/tests/test_service.py` |
| Health/API/WebSocket/export schema | `backend/tests/test_api.py` |
| Replay-to-label-to-report-to-export flow | `backend/tests/test_integration_replay.py` |
| UI state, matrix inspection, research/quality/method pages | `frontend/src/**/*.test.tsx` |
| Default 21×36 latency | `scripts/benchmark_model.py` |

## Packaged runtime gate

```bash
docker compose up --build -d
uv run python scripts/verify_runtime.py --base-url http://localhost:3000
docker compose ps
docker compose logs --tail=100 app
```

Expected checker fields: `status: PASS`, shape `[21, 36]`, at least three unique advancing forecast IDs, `fault_seen: true`, `recovered_after_fault: true`, and a nonzero CSV byte count. Compose health requires both process liveness and a ready model snapshot.

## Claims boundary

The packaged replay is deterministic synthetic data. It validates the complete runtime and abnormal-state behavior but is not evidence of market accuracy. `artifacts/demo-backtest/summary.json` must say `COMPACT_DEMO_NOT_FULL_CYCLE`.

A full-cycle calibration claim is allowed only when a separately acquired public/authorized dataset produces a coverage report with:

- `is_full_cycle: true`
- `valid: true`
- disclosure `FULL_CYCLE`
- nonzero minimum-qualified LOW, MEDIUM, HIGH, and SHOCK counts
- verified checksum and complete declared coarse/high-resolution ranges

Network probes and long downloads are optional evidence because source availability and download size are external. Record failures verbatim; do not substitute synthetic replay and call it live or historical.

## Fresh real-data evidence (2020 BTC)

The 2020 Binance public 1-minute OHLC run completed during delivery. It contained 525,788 bars with zero missing monthly archives, produced 366 walk-forward forecast origins and 10,980 cell labels, and passed the 50-sample-per-regime gate with LOW 126, MEDIUM 70, HIGH 56, and SHOCK 114. Labels are explicitly `BAR_APPROX`. The compact machine-readable record is in `docs/evidence/2020-btc-full-cycle-summary.json`; commands in the README reproduce the full artifacts.

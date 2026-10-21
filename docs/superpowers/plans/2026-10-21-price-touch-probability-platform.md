# Price-Touch Probability Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a zero-paid-key, Docker-started web application that publishes a complete price-touch probability matrix every second and validates its calibration with chronological, regime-aware backtests.

**Architecture:** A Python/FastAPI computation service owns normalized market events, quality state, forecasting, labeling, persistence, and WebSocket snapshots. A React/ECharts client renders live, research, quality, and methodology views; deterministic replay is the offline default, while optional public adapters are isolated behind the same market-event interface.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, NumPy, Polars, DuckDB, PyArrow/Parquet, pytest/Hypothesis; React 18, TypeScript, Vite, ECharts, Vitest/Testing Library; Docker Compose and Make.

**Spec:** `docs/superpowers/specs/2026-10-21-price-touch-probability-design.md`

## Global Constraints

- No paid key is required for the primary acceptance path.
- `docker compose up --build` is the canonical start command.
- Default output is 21 fixed-width price intervals by 36 disjoint five-second windows, refreshed once per second.
- Forecast geometry is frozen at issuance and all feature, bootstrap, regime, and calibration state is strictly past-only.
- Offline demo replay is deterministic; synthetic fault fixtures are never presented as historical evidence.
- Tick-exact and bar-approximate labels, plus `LIVE`, `DELAYED`, `REPLAY`, `DEGRADED`, `STALE`, and `MARKET_CLOSED` states, remain distinguishable in APIs and UI.
- A source or computation failure must be visible and must never be disguised as a fresh live result.

## Review Focus

- A trade exactly on a shared price boundary belongs to only the right-hand interval; Task 2 pins the convention with a boundary test.
- A discrete jump across an interval without an eligible print is not a touch; Task 2 pins this with tick-exact labeling and Task 5 with simulated jump paths.
- A late event after label finalization must not silently rewrite headline results; Task 3 exercises bounded lateness and late counters.
- A walk-forward calibrator must not read the label being predicted or any later regime thresholds; Task 6 exercises a sentinel future-data leakage test.
- A process can be healthy while forecasts are stale or a market is closed; Task 7 exercises separate liveness, readiness, freshness, and market-state API fields.

---

### Task 1: Reproducible project shell and typed configuration

**Files:**
- Create: `pyproject.toml`
- Create: `Makefile`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `backend/price_touch/__init__.py`
- Create: `backend/price_touch/config.py`
- Create: `backend/price_touch/domain.py`
- Create: `backend/tests/test_config.py`
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/types.ts`

**Interfaces:**
- Produces: `Settings`, `AssetConfig`, `MatrixConfig`, `MarketEvent`, `SourceStatus`, `QualityFlag`, `ForecastSnapshot`, and matching JSON/TypeScript field names used by every later task.

- [ ] **Step 1: Write failing configuration and schema tests**

Test that defaults resolve to 21 intervals, 36 windows, five-second delay/window, one-second publication cadence, positive asset tick/step sizes, and rejected unsafe matrix sizes. Assert a minimal `ForecastSnapshot` serializes with explicit source mode, freshness, model version, frozen bounds, and matrix shapes.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `uv run pytest backend/tests/test_config.py -q`
Expected: FAIL because the package and domain schemas do not exist.

- [ ] **Step 3: Implement the project metadata, settings, and domain schemas**

Use Pydantic for external schemas and integer price ticks for interval bounds. Keep runtime defaults in one settings module and generate or manually mirror the stable snapshot schema in `frontend/src/types.ts`.

- [ ] **Step 4: Run tests and static import checks**

Run: `uv run pytest backend/tests/test_config.py -q && uv run python -c "from price_touch.config import Settings; print(Settings().matrix.interval_count)"`
Expected: PASS and `21`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml Makefile .gitignore .env.example docker-compose.yml Dockerfile backend frontend
git commit -m "build: scaffold probability research platform"
```

### Task 2: Frozen matrix geometry and exact touch labeling

**Files:**
- Create: `backend/price_touch/geometry.py`
- Create: `backend/price_touch/labeling.py`
- Create: `backend/tests/test_geometry.py`
- Create: `backend/tests/test_labeling.py`

**Interfaces:**
- Consumes: `MatrixConfig`, normalized `MarketEvent`, and integer tick prices from Task 1.
- Produces: `build_geometry(origin_ns: int, origin_price_ticks: int, config: MatrixConfig) -> ForecastGeometry` and `label_forecast(geometry: ForecastGeometry, events: Sequence[MarketEvent], precision: LabelPrecision) -> TouchLabels`.

- [ ] **Step 1: Write failing geometry tests**

Assert exactly 21 adjacent half-open intervals centered on the origin price and 36 disjoint windows `[+5,+10)` through `[+180,+185)`. Assert a boundary tick is assigned to the right interval only and invalid even tick widths are rejected when they cannot center exactly.

- [ ] **Step 2: Verify geometry tests fail for missing behavior**

Run: `uv run pytest backend/tests/test_geometry.py -q`
Expected: FAIL because `build_geometry` is missing.

- [ ] **Step 3: Implement decimal-safe geometry**

Represent all boundaries in instrument ticks and return immutable geometry containing absolute event-time window bounds.

- [ ] **Step 4: Write failing label tests**

Cover exact touch, no touch, repeat touch, events on both time-window boundaries, one path touching multiple intervals, tick jump-over-without-touch, and a separately flagged OHLC-range approximation.

- [ ] **Step 5: Verify label tests fail, then implement the labeler**

Run RED: `uv run pytest backend/tests/test_labeling.py -q`
Implement event-time filtering without interpolating tick trades. Run GREEN: `uv run pytest backend/tests/test_geometry.py backend/tests/test_labeling.py -q`.

- [ ] **Step 6: Commit**

```bash
git add backend/price_touch/geometry.py backend/price_touch/labeling.py backend/tests
git commit -m "feat: define frozen touch events"
```

### Task 3: Deterministic replay and market-data quality state

**Files:**
- Create: `backend/price_touch/market/base.py`
- Create: `backend/price_touch/market/replay.py`
- Create: `backend/price_touch/market/quality.py`
- Create: `backend/price_touch/market/clock.py`
- Create: `backend/tests/market/test_replay.py`
- Create: `backend/tests/market/test_quality.py`
- Create: `data/demo/manifest.json`
- Create: `data/demo/market_events.csv`
- Create: `data/demo/fault_scenarios.json`

**Interfaces:**
- Consumes: `MarketEvent`, source status schemas, and injected event/monotonic clocks.
- Produces: `MarketAdapter.events() -> AsyncIterator[MarketEvent]`, `ReplayAdapter`, and `QualityGate.accept(event: MarketEvent) -> QualityDecision` with counters and state transitions.

- [ ] **Step 1: Write failing replay-clock tests**

Assert the same fixture and seed emit identical event order/timestamps, replay speed does not change event-time semantics, and pause/resume never duplicates an event.

- [ ] **Step 2: Verify RED, implement clock and replay, then verify GREEN**

Run RED/GREEN: `uv run pytest backend/tests/market/test_replay.py -q`.

- [ ] **Step 3: Write failing quality-state tests**

Exercise stable-ID duplicates, in-window reordering, too-late events after finalization, invalid/nonpositive prices, source gaps, stale transition, recovery, clock skew, and `MARKET_CLOSED` distinct from transport failure.

- [ ] **Step 4: Verify RED, implement the quality gate, then verify GREEN**

Run: `uv run pytest backend/tests/market/test_quality.py -q`.
Expected: PASS with reason-coded counters and deterministic state changes.

- [ ] **Step 5: Add provenance-complete demo fixtures**

Keep ordinary observations and synthetic fault scenarios distinct in the manifest. Tests must reject a fixture whose manifest omits source kind, time range, resolution, label precision, row count, or checksum.

- [ ] **Step 6: Commit**

```bash
git add backend/price_touch/market backend/tests/market data/demo
git commit -m "feat: add deterministic market replay"
```

### Task 4: Public zero-key adapters with explicit fallback semantics

**Files:**
- Create: `backend/price_touch/market/binance.py`
- Create: `backend/price_touch/market/commodities.py`
- Create: `backend/price_touch/market/supervisor.py`
- Create: `backend/tests/market/test_adapters.py`
- Create: `scripts/probe_public_sources.py`
- Create: `docs/data-sources.md`

**Interfaces:**
- Consumes: `MarketAdapter`, normalized domain events, and quality states from Tasks 1 and 3.
- Produces: `BinanceTradeAdapter`, selected gold/oil public quote adapter, and `AdapterSupervisor.run() -> AsyncIterator[MarketEvent]` with bounded exponential reconnect and no implicit replay masquerading as live data.

- [ ] **Step 1: Verify candidate source contracts before selecting them**

Use official/provider documentation and a small read-only probe to record authentication, symbol semantics, timestamp fields, rate limits, and whether quotes are live or delayed. Put the checked date and limitations in `docs/data-sources.md`; do not promote a source that requires an undisclosed key or prohibited scraping.

- [ ] **Step 2: Write failing adapter contract tests**

With recorded protocol fixtures, assert normalization, symbol mapping, timestamp parsing, duplicate IDs, delayed-state declaration, reconnect/backoff ceilings, and visible terminal failure. Add opt-in network smoke tests that are excluded from `make verify` but callable explicitly.

- [ ] **Step 3: Verify RED, implement adapters and supervisor, then verify GREEN**

Run: `uv run pytest backend/tests/market/test_adapters.py -q`.
Expected: PASS without network access.

- [ ] **Step 4: Run and record the opt-in smoke probe when network is available**

Run: `uv run python scripts/probe_public_sources.py`
Expected: machine-readable status for BTC, gold, and oil; failures remain visible and do not fail offline replay acceptance.

- [ ] **Step 5: Commit**

```bash
git add backend/price_touch/market backend/tests/market scripts/probe_public_sources.py docs/data-sources.md
git commit -m "feat: integrate public market sources"
```

### Task 5: Analytic, bootstrap, jump, and calibration probability engine

**Files:**
- Create: `backend/price_touch/model/features.py`
- Create: `backend/price_touch/model/regime.py`
- Create: `backend/price_touch/model/analytic.py`
- Create: `backend/price_touch/model/bootstrap.py`
- Create: `backend/price_touch/model/calibration.py`
- Create: `backend/price_touch/model/engine.py`
- Create: `backend/tests/model/test_features.py`
- Create: `backend/tests/model/test_models.py`
- Create: `backend/tests/model/test_calibration.py`
- Create: `backend/tests/model/test_engine.py`

**Interfaces:**
- Consumes: past-only normalized events, `ForecastGeometry`, model settings, forecast ID, and an optional past-only `CalibrationArtifact`.
- Produces: `FeatureState`, `Regime`, `AnalyticModel.predict(...) -> ProbabilityMatrix`, `BootstrapModel.predict(...) -> ProbabilityMatrix`, `fit_calibrator(matured_rows, cutoff_ns) -> CalibrationArtifact`, and `ProbabilityEngine.forecast(...) -> ModelResult`.

- [ ] **Step 1: Write failing past-only feature and regime tests**

Append sentinel future prices and assert features/regime at an earlier cutoff are byte-for-byte unchanged. Cover zero returns, sparse history, shock classification, and robust finite scale estimates.

- [ ] **Step 2: Verify RED, implement features/regimes, then verify GREEN**

Run: `uv run pytest backend/tests/model/test_features.py -q`.

- [ ] **Step 3: Write failing analytic and bootstrap behavior tests**

Assert complete finite matrices in `[0,1]`, deterministic bootstrap output for a forecast ID, increased near-term touch probability under higher volatility for representative cells, no automatic touch across a discrete jump, and one path set shared across cells.

- [ ] **Step 4: Verify RED, implement minimal models, then verify GREEN**

Run: `uv run pytest backend/tests/model/test_models.py -q`.

- [ ] **Step 5: Write failing calibration and fallback tests**

Assert no calibrator uses rows at/after its cutoff, sufficient monotone samples produce isotonic mapping, sparse samples return shrinkage or `UNCALIBRATED`, output remains finite, primary timeout reduces paths then falls back to analytic, and invalid output returns no fresh snapshot.

- [ ] **Step 6: Verify RED, implement calibration/orchestration, then verify GREEN**

Run: `uv run pytest backend/tests/model/test_calibration.py backend/tests/model/test_engine.py -q`.

- [ ] **Step 7: Benchmark the default 756-cell forecast**

Add a non-flaky benchmark command that reports p50/p95 computation time and path count without asserting hardware-specific milliseconds in unit tests.

- [ ] **Step 8: Commit**

```bash
git add backend/price_touch/model backend/tests/model
git commit -m "feat: estimate calibrated touch probabilities"
```

### Task 6: Walk-forward backtest, maturity labeling, and coverage reports

**Files:**
- Create: `backend/price_touch/backtest/runner.py`
- Create: `backend/price_touch/backtest/metrics.py`
- Create: `backend/price_touch/backtest/coverage.py`
- Create: `backend/price_touch/backtest/storage.py`
- Create: `backend/tests/backtest/test_walk_forward.py`
- Create: `backend/tests/backtest/test_metrics.py`
- Create: `backend/tests/backtest/test_coverage.py`
- Create: `scripts/download_history.py`
- Create: `scripts/run_backtest.py`

**Interfaces:**
- Consumes: chronological events, forecast engine, exact/approximate labeler, dataset manifest, and backtest configuration.
- Produces: `WalkForwardRunner.run() -> BacktestRun`, cell-level Parquet, aggregate DuckDB tables, `compute_metrics(rows) -> MetricReport`, and `validate_cycle_coverage(manifest, rows) -> CoverageReport`.

- [ ] **Step 1: Write failing walk-forward and maturity tests**

Use sentinel future values to prove forecasts, regime thresholds, bootstrap pools, and calibrators are past-only. Assert labels appear only after the final observation window matures and origins follow the configured five-second evaluation cadence.

- [ ] **Step 2: Verify RED, implement the chronological runner, then verify GREEN**

Run: `uv run pytest backend/tests/backtest/test_walk_forward.py -q`.

- [ ] **Step 3: Write failing metric tests against hand-calculated fixtures**

Pin Brier score, clipped log loss, ECE bin accounting, calibration slope/intercept behavior, coverage/skips, baseline skill, and separate aggregation by asset/regime/horizon/distance/label precision. Include dependence-aware block-bootstrap confidence intervals with a fixed seed.

- [ ] **Step 4: Verify RED, implement metrics/storage, then verify GREEN**

Run: `uv run pytest backend/tests/backtest/test_metrics.py -q`.

- [ ] **Step 5: Write failing full-cycle coverage tests**

Assert validation fails when low, medium, high, shock, exact time coverage, checksums, or high-resolution sample thresholds are missing; assert demo output is labeled compact rather than full-cycle.

- [ ] **Step 6: Verify RED, implement coverage/downloader/reporting, then verify GREEN**

Run: `uv run pytest backend/tests/backtest/test_coverage.py -q`.

- [ ] **Step 7: Run the deterministic fast backtest**

Run: `uv run python scripts/run_backtest.py --dataset data/demo/manifest.json --output artifacts/demo-backtest`
Expected: successful report with raw/baseline/final metrics, regime breakdown, coverage disclosure, Parquet details, and JSON summary.

- [ ] **Step 8: Commit**

```bash
git add backend/price_touch/backtest backend/tests/backtest scripts/download_history.py scripts/run_backtest.py
git commit -m "feat: add walk-forward calibration research"
```

### Task 7: Snapshot persistence, runtime service, HTTP API, and WebSocket stream

**Files:**
- Create: `backend/price_touch/storage.py`
- Create: `backend/price_touch/service.py`
- Create: `backend/price_touch/api.py`
- Create: `backend/price_touch/main.py`
- Create: `backend/tests/test_service.py`
- Create: `backend/tests/test_api.py`
- Create: `backend/tests/test_integration_replay.py`

**Interfaces:**
- Consumes: adapters, quality gate, geometry, probability engine, labeler, backtest storage, and settings.
- Produces: `ForecastService.run()`, atomic snapshot persistence, `/api/v1/health`, `/config`, `/snapshots`, `/backtests`, `/exports`, and `/ws/snapshots`.

- [ ] **Step 1: Write failing service lifecycle tests**

Assert one immutable snapshot per replay second, slow subscribers cannot block forecasting, matured labels attach to the correct frozen forecast, partial matrices are never persisted, and stale last-success data is not republished with a new forecast ID.

- [ ] **Step 2: Verify RED, implement storage/service, then verify GREEN**

Run: `uv run pytest backend/tests/test_service.py -q`.

- [ ] **Step 3: Write failing API contract tests**

Assert liveness differs from readiness/freshness, `MARKET_CLOSED` differs from failure, configuration validation returns actionable errors, snapshot/export metadata contains frozen bounds, WebSocket clients receive versioned full snapshots, and JSON/CSV exports preserve flags and label precision.

- [ ] **Step 4: Verify RED, implement API/WebSocket endpoints, then verify GREEN**

Run: `uv run pytest backend/tests/test_api.py -q`.

- [ ] **Step 5: Write and run the deterministic end-to-end replay test**

Run replay through ingestion, quality transitions, forecasting, snapshot persistence, maturation, labeling, report generation, API retrieval, WebSocket delivery, and export.
Run: `uv run pytest backend/tests/test_integration_replay.py -q`.

- [ ] **Step 6: Commit**

```bash
git add backend/price_touch backend/tests
git commit -m "feat: serve realtime probability snapshots"
```

### Task 8: Four-view React acceptance interface

**Files:**
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/state.ts`
- Create: `frontend/src/styles.css`
- Create: `frontend/src/components/StatusBar.tsx`
- Create: `frontend/src/views/LiveMatrix.tsx`
- Create: `frontend/src/views/Research.tsx`
- Create: `frontend/src/views/DataQuality.tsx`
- Create: `frontend/src/views/Methodology.tsx`
- Create: `frontend/src/**/*.test.tsx`

**Interfaces:**
- Consumes: versioned HTTP/WebSocket schemas from Task 7.
- Produces: a responsive single-page UI with `/`, `/research`, `/quality`, and `/methodology` routes.

- [ ] **Step 1: Write failing state and status-visibility tests**

Assert reconnect handling, stale snapshot rejection, stable matrix axes, visible `LIVE/DELAYED/REPLAY/DEGRADED/STALE/MARKET_CLOSED` labels, and prominent source age/model version.

- [ ] **Step 2: Verify RED, implement state/API/status shell, then verify GREEN**

Run: `cd frontend && npm test -- --run`

- [ ] **Step 3: Write failing live-matrix interaction tests**

Assert asset selection, matrix dimensions, stable color scale, cell inspection of frozen bounds and three probability variants, validated configuration controls, and no loss of quality flags.

- [ ] **Step 4: Verify RED, implement Live Matrix, then verify GREEN**

Run: `cd frontend && npm test -- --run`

- [ ] **Step 5: Write failing research, quality, and methodology view tests**

Assert reliability/metric/regime filters, dataset metadata and coverage disclosure, quality counters/timeline, exact event definition, assumptions, and limitation copy.

- [ ] **Step 6: Verify RED, implement remaining views, then verify GREEN**

Run: `cd frontend && npm test -- --run && npm run typecheck && npm run build`

- [ ] **Step 7: Commit**

```bash
git add frontend
git commit -m "feat: visualize live and calibrated probabilities"
```

### Task 9: Container delivery, acceptance guide, and full verification

**Files:**
- Modify: `Dockerfile`
- Modify: `docker-compose.yml`
- Modify: `Makefile`
- Create: `README.md`
- Create: `docs/methodology.md`
- Create: `docs/acceptance.md`
- Create: `scripts/verify_runtime.py`

**Interfaces:**
- Consumes: all prior tasks.
- Produces: one-command production image, offline demo acceptance flow, long-data commands, and recorded verification artifacts.

- [ ] **Step 1: Write failing runtime acceptance checks**

The checker waits for liveness and model readiness, receives at least three advancing replay snapshots, verifies the 21x36 shape and finite probabilities, observes a configured fault state and recovery, requests an export, and confirms the UI entry point.

- [ ] **Step 2: Verify the checker fails before final packaging**

Run: `uv run python scripts/verify_runtime.py --base-url http://localhost:3000`
Expected: FAIL until the packaged service is running and correctly routed.

- [ ] **Step 3: Complete the multi-stage image and Compose health checks**

Build the React assets, install the Python application, copy only declared demo artifacts, run as a non-root user, and expose one application port. Health checks distinguish process liveness from data/model readiness.

- [ ] **Step 4: Write the three-minute acceptance and methodology documentation**

Document exact commands, expected states, event semantics, source provenance, model trade-offs, backtest coverage, current limitations, exports, and public-source failure behavior.

- [ ] **Step 5: Run the full local verification suite**

Run: `make verify`
Expected: backend tests, frontend tests, lint/type checks, production build, and deterministic fast backtest all pass with no hidden network dependency.

- [ ] **Step 6: Run container acceptance and inspect fresh evidence**

Run: `docker compose up --build -d`, then `uv run python scripts/verify_runtime.py --base-url http://localhost:3000`, then inspect `docker compose logs` and `docker compose ps`.
Expected: three advancing matrices, visible fault/recovery, successful export, healthy process, and ready demo model.

- [ ] **Step 7: Run performance and optional network evidence**

Record p50/p95 default-matrix compute duration and delivered snapshot cadence. Run public-source probes and the long historical download/backtest only when network/time permits; document exact unverified portions otherwise.

- [ ] **Step 8: Re-read the specification requirement by requirement**

Map every acceptance requirement to test, runtime, report, or UI evidence. Fix any uncovered gap before claiming completion.

- [ ] **Step 9: Commit**

```bash
git add Dockerfile docker-compose.yml Makefile README.md docs scripts/verify_runtime.py
git commit -m "docs: package reproducible acceptance demo"
```

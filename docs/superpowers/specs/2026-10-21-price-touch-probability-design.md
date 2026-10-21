# Price-Touch Probability Research Platform Design

## 1. Purpose

Build a zero-paid-key, one-command web application that estimates and displays, once per second, the probability that BTC, gold, or crude-oil trades touch each configured price interval during each future observation window. The same system must preserve issued forecasts, generate future touch labels, and evaluate calibration across normal and abnormal market regimes.

The product is an inspectable research system rather than a trading signal. Every result must identify its data source, data freshness, model version, forecast origin, calibration status, and any degraded behavior.

## 2. Acceptance Experience

The primary acceptance path is:

1. Run `docker compose up --build` without credentials.
2. Open `http://localhost:3000`.
3. Start the deterministic demo replay and observe the full matrix update once per second.
4. Inspect an individual cell's frozen boundaries, raw probability, calibrated probability, model state, and quality flags.
5. Open the research panel and compare predictions with realized touch frequencies across volatility regimes.
6. Open the data-quality panel and observe a replayed gap, jump, stale-source period, and recovery.

The repository also provides `make verify` for all automated checks and a fast deterministic backtest, plus a separate command for downloading larger public historical datasets and running the long backtest.

## 3. Explicit Scope

### Included

- Assets: BTC, gold, and crude oil.
- A configurable fixed price step `d` per asset.
- A configurable matrix, defaulting to 21 price intervals and 36 disjoint five-second observation windows from `+5s` through `+185s`.
- One complete immutable matrix snapshot per second.
- Public live/delayed adapters where reliable zero-key access is available.
- Deterministic replay that works offline and is the default acceptance mode.
- Historical ingestion, walk-forward backtesting, calibration analysis, regime analysis, and JSON/CSV export.
- Explicit handling of jumps, extreme volatility, delayed or interrupted data, duplicates, out-of-order events, computation overruns, and market closure.

### Excluded

- Order placement, portfolio advice, or profitability claims.
- Paid data vendors and required API credentials.
- A distributed queue, Redis, or a separate database server.
- Deep-learning models or per-cell classifiers that require an impractical training corpus.
- Claims that bar-derived labels have tick-level precision.

## 4. Exact Event Definition

For a forecast issued at event time `t`, let `P_t` be the latest eligible trade price. The price grid is frozen for the lifetime of that forecast. For integer interval index `k`, the half-open interval is:

`I_k(t) = [P_t + (k - 1/2)d, P_t + (k + 1/2)d)`.

With default five-second windows and a five-second observation delay, window `j` is:

`W_j(t) = [t + 5s + 5j, t + 10s + 5j)`, for `j = 0..35`.

The cell label is one if at least one eligible trade with event time in `W_j(t)` has a transaction price in `I_k(t)`, and zero otherwise. Windows are disjoint, not cumulative. A path may touch multiple intervals within a window, so cell probabilities in a column are not a categorical distribution and need not sum to one.

Interval boundaries use decimal-safe integer price ticks internally. A price exactly on a shared boundary belongs only to the interval on its right. Forecast records include the exact interval bounds and window bounds used at issuance.

Tick trades produce `TICK_EXACT` labels. When only OHLC bars are available, an interval is approximately touched if the bar's observed low-high range intersects it; those labels are stored and reported separately as `BAR_APPROX`.

## 5. Architecture

The repository is a Python/TypeScript monorepo with a single production application container:

- Python 3.12 backend using FastAPI, NumPy, Polars, and DuckDB.
- React, TypeScript, Vite, and Apache ECharts frontend.
- Parquet for portable market and backtest artifacts.
- DuckDB for local analytical queries and reports.
- WebSocket delivery of immutable matrix snapshots.
- The compiled frontend is served by FastAPI in the production image.

Runtime components have narrow interfaces:

1. **Market adapters** emit normalized trades or bars and source-health events.
2. **Quality gate** deduplicates, bounds out-of-order arrival, detects gaps, and classifies freshness.
3. **Feature engine** maintains rolling returns, robust scale estimates, jump statistics, and volatility regime state.
4. **Probability engine** produces the analytic baseline and Monte Carlo raw matrix from one shared set of paths.
5. **Calibration engine** applies only calibration artifacts trained strictly before the forecast origin.
6. **Snapshot service** creates immutable, versioned forecast records and broadcasts them.
7. **Labeler** joins matured forecasts to future observations using the frozen event definition.
8. **Backtester** performs walk-forward evaluation and writes cell-level and aggregate artifacts.
9. **API/UI** exposes live state, research results, quality diagnostics, configuration, and exports.

The application must keep the computation loop independent of connected browsers. A slow or disconnected browser cannot block market ingestion or forecast generation.

## 6. Data Modes and Provenance

The application exposes four mutually visible states:

- `LIVE`: eligible current public trade data.
- `DELAYED`: a functioning source whose quote age or vendor semantics are delayed.
- `REPLAY`: deterministic stored observations driven by a replay clock.
- `DEGRADED`: a fallback model, reduced path count, or stale last-success snapshot.

`MARKET_CLOSED` is a market state, not a transport error. `STALE` is a freshness flag that prevents an old quote from being presented as a new forecast origin.

Each stored dataset has a manifest containing asset, instrument, vendor, source URL template, acquisition time, time range, resolution, timezone, label precision, row count, missing-rate summary, and checksum. Demo fixtures must state whether they are redistributable real observations or deterministic synthetic fault scenarios. Synthetic observations must never be described as historical market evidence.

The default offline replay combines compact real-data slices for ordinary regimes with clearly marked deterministic fault fixtures for gaps, jumps, and reconnects. The long-backtest downloader obtains public data without a paid key; source availability and instrument semantics are verified during implementation and documented rather than hard-coded as unsupported claims.

## 7. Probability Estimation

### 7.1 Analytic baseline

A drifted diffusion first-passage approximation provides a fast, explainable baseline and fallback. It uses robust rolling drift and volatility estimates and returns a complete matrix within the per-second budget. The UI and exported artifacts identify analytic results separately from final calibrated results.

### 7.2 Regime-conditioned bootstrap Monte Carlo

The primary model:

1. Computes rolling returns and robust realized-volatility features using only observations available at the forecast origin.
2. Assigns a low, medium, high, or shock regime from thresholds fitted on past data.
3. Samples contiguous historical return blocks from compatible past regimes, preserving short-run dependence and volatility clustering.
4. Models empirically observed discrete jumps separately from within-block diffusion.
5. Simulates paths at the finest supported event grid using a deterministic seed derived from forecast ID in replay/backtest mode.
6. Uses each path's within-window observations and extrema to evaluate every interval in vectorized batches.

Continuous diffusion may use a Brownian-bridge correction between simulation points. A discrete jump may skip an interval; skipped intervals are not automatically counted as touched. One simulated path set produces every matrix cell, avoiding per-cell simulation.

### 7.3 Calibration

Calibration artifacts are trained walk-forward from matured historical forecasts only. The model pools evidence by asset, normalized distance from origin, horizon bucket, and regime so rare cells do not receive unstable independent calibrators. Isotonic calibration is used only above a documented effective-sample threshold; otherwise the system falls back to a shrinkage mapping or leaves the raw probability unchanged with `UNCALIBRATED` status.

Every cell exposes raw probability, final probability, calibration method, effective sample size, and quality flags. Probabilities are finite and clamped to `[0, 1]` only at the numerical boundary, not replaced with hand-authored values.

## 8. Real-Time Budget and Snapshot Semantics

The target is one snapshot per second on a normal laptop. Path simulation is shared across cells and vectorized. Each snapshot contains:

- `forecast_id`, asset, instrument, event-time origin, and publication time.
- Frozen price-interval and observation-window bounds.
- Raw, baseline, and calibrated probability matrices.
- Source mode, source age, model version, regime, path count, compute duration, and quality flags.

If the primary computation exceeds its budget, the engine first reduces path count within configured limits, then uses the analytic fallback. If neither produces a valid fresh forecast, the service retains the last successful snapshot and marks it `STALE`; it does not republish it as newly computed. Snapshot generation is atomic so clients never observe a partially updated matrix.

## 9. Walk-Forward Backtesting and Full-Cycle Coverage

The backtester processes forecast origins chronologically. At each origin, all feature thresholds, bootstrap pools, model parameters, and calibration artifacts are derived only from earlier data. Random train/test shuffling is prohibited.

The headline evaluation samples forecast origins every five seconds to reduce redundant origins. A one-second diagnostic mode is available. Dependence-aware block bootstrap intervals accompany aggregate metrics.

Reported metrics include:

- Brier score and skill relative to the analytic baseline.
- Log loss with stable numerical clipping reported as an evaluation detail.
- Expected calibration error with disclosed bins.
- Calibration intercept and slope.
- Reliability bins with observed frequency, forecast mean, effective sample count, and confidence interval.
- Coverage and skipped-forecast counts.

Metrics are available overall and by asset, price-distance bucket, observation-window bucket, label precision, and volatility regime. The research panel compares analytic baseline, raw Monte Carlo, and final calibrated probabilities.

Full-cycle coverage is defined by a manifest-backed evaluation period containing low-, medium-, high-volatility, and shock regimes. A long coarse-resolution series establishes regime coverage; eligible high-resolution observations within each regime provide event labels. Reports disclose exact temporal coverage and never claim that a compact demo slice is the full-cycle evaluation. The long run emits a machine-readable coverage report and fails validation when a required regime lacks enough high-resolution samples.

## 10. Exceptional Conditions

- **Gap/jump:** Retain real extreme observations. Model them separately; do not fabricate touches across a discrete jump.
- **Extreme volatility:** Enter `SHOCK` regime and widen uncertainty/quality warnings. Robust parameter estimation may limit influence on estimates but must not delete realized labels.
- **Duplicate:** Deduplicate by stable vendor trade ID, or a documented composite key when no ID exists.
- **Out of order:** Accept within a bounded event-time lateness window. Later arrivals are counted in quality statistics and do not silently rewrite finalized headline results.
- **Data interruption:** Reconnect with bounded exponential backoff. After freshness expiry, stop fresh forecasts and expose `STALE`; optionally switch to an explicitly labeled replay selected by the operator.
- **Market closure:** Emit `MARKET_CLOSED`, keep the last quote for reference, and do not count closed time as a live-source outage.
- **Invalid price/time:** Quarantine the record, increment a reason-coded counter, and continue only if source health remains acceptable.
- **Insufficient history:** Use the analytic baseline with `UNCALIBRATED` and `INSUFFICIENT_HISTORY` flags.
- **Clock discontinuity:** Use event time for labels and a monotonic clock for scheduling; expose clock-skew diagnostics.

## 11. User Interface

### Live Matrix

- Asset and data-mode selector.
- Matrix heatmap with fixed, labeled axes and a stable color scale.
- Cell inspector showing bounds, raw/baseline/final probability, sample information, and flags.
- Current price, regime, source age, update time, path count, compute duration, and model version.
- Controls for fixed step, interval count, window length, horizon, and replay speed, validated against safe bounds.

### Research and Backtest

- Reliability curve and probability-bin table.
- Brier, log loss, ECE, calibration slope/intercept, and coverage.
- Baseline/raw/calibrated comparison.
- Filters and side-by-side results for volatility regimes, assets, horizons, and label precision.
- Exact dataset and configuration metadata for every displayed run.

### Data Quality

- Current adapter state and reconnect status.
- Freshness, missing intervals, duplicate count, late count, invalid records, and computation overruns.
- Timeline of state changes and fallback reasons.

### Methodology

- Exact event definition and half-open boundary convention.
- Model explanation, assumptions, dataset provenance, limitations, and reproducibility commands.

The interface must remain usable while receiving updates and must not redraw axes in a way that makes adjacent snapshots visually incomparable.

## 12. APIs and Exports

The backend provides health/configuration endpoints, current and historical snapshot endpoints, backtest-run endpoints, report endpoints, CSV/JSON exports, and a WebSocket snapshot stream. Schemas are versioned and generated into frontend types where practical.

`/health` reports process health separately from data freshness and model readiness. A running HTTP server with stale data is not reported as fully ready.

Exports contain frozen bounds and metadata, not only a matrix of anonymous numbers. Backtest exports include forecast ID, cell identity, probability variants, realized label, label precision, regime, and quality flags.

## 13. Testing and Verification

Backend unit and property tests cover:

- Half-open interval boundaries and decimal tick conversion.
- Disjoint observation-window boundaries.
- Exact tick touch, no touch, repeated touch, and jump-over-without-touch.
- Duplicate, out-of-order, stale, and gap handling.
- No future observations in feature, bootstrap, regime, or calibration state.
- Deterministic replay and Monte Carlo seeds.
- Finite probabilities within `[0, 1]` and complete matrix shapes.
- Primary-model timeout and analytic fallback.
- Label precision separation and full-cycle coverage validation.

Frontend tests cover state badges, matrix rendering from a fixed snapshot, cell inspection, stale-state visibility, and research filters. Integration tests run a deterministic replay through ingestion, forecast, maturation, labeling, report generation, WebSocket delivery, and export.

Performance verification records matrix computation latency and update cadence for the default 756-cell configuration. `make verify` must run the complete test, type-check, lint, build, and deterministic fast-backtest suite. Verification reports actual commands and outputs; unavailable long public-data runs remain explicitly unverified rather than implied complete.

## 14. Delivery Constraints

- No paid key is required for the primary acceptance path.
- `docker compose up --build` is the canonical start command.
- Demo behavior is deterministic and works offline after the image is built.
- Public-source failure cannot prevent offline acceptance.
- Secrets, if an operator later adds optional sources, come only from environment variables and are never committed.
- The README contains a three-minute acceptance guide, architecture overview, event definition, commands, provenance, and known limitations.
- The implementation favors a complete, defensible vertical slice over infrastructure that does not contribute to the stated acceptance criteria.

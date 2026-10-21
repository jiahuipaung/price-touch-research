# Methodology

## Cell definition

At forecast event time `t`, let `Pₜ` be the latest eligible price and `d` the configured step in integer ticks. For interval index `k`:

```text
Iₖ(t) = [Pₜ + (k - 1/2)d, Pₜ + (k + 1/2)d)
```

For the default five-second delay and width, window `j` is:

```text
Wⱼ(t) = [t + 5s + 5j, t + 10s + 5j), j = 0…35
```

The cell label is 1 if any eligible observed price in `Wⱼ(t)` belongs to `Iₖ(t)`. Bounds are half-open, so an observation on a shared boundary belongs only to the interval on its right. Windows are disjoint. Column probabilities need not sum to one because a path can touch several bands.

`TICK_EXACT` uses individual trades. `BAR_APPROX` marks intersection of an observed OHLC low/high range and an interval and is reported separately.

## Estimators

The analytic baseline is a drifted-diffusion first-passage approximation built from robust past-only drift and scale. It is fast enough to serve as an explainable baseline and bounded fallback.

The primary estimator samples contiguous blocks of historical returns with a deterministic forecast-ID seed. One simulated path set evaluates all cells, preserving short-run dependence and avoiding one model per cell. Discrete sampled jumps evaluate only actually sampled path points; skipped intermediate bands are not counted as touched. A timeout reduces paths first and then uses the analytic fallback, both with explicit flags.

The calibration layer consumes only labels whose full observation horizon matured before the new origin. It uses isotonic calibration when sample support is sufficient, otherwise shrinkage or identity with `UNCALIBRATED`. The backtester repeats the same ordering at every origin.

## Evaluation

Reports contain Brier score and analytic-baseline skill, clipped log loss, expected calibration error, logistic calibration intercept/slope, reliability bins, coverage/skips, and a dependence-aware block-bootstrap Brier interval. Results are grouped by asset, regime, horizon, distance, and label precision.

Full-cycle validation requires manifest-backed temporal coverage and minimum samples in LOW, MEDIUM, HIGH, and SHOCK regimes. The bundled fast demo always emits `COMPACT_DEMO_NOT_FULL_CYCLE`; a UI screenshot cannot upgrade that claim.

## Exceptional conditions

- Duplicates are rejected by instrument/trade ID.
- Bounded reordering is accepted; arrivals behind the finalized watermark are counted and rejected.
- Invalid prices are quarantined.
- Gaps, stale sources, transport errors, and market closure remain distinct states.
- A transport failure does not silently switch a live adapter to replay.
- A stale successful snapshot is retained but never republished with a new forecast ID.
- Extreme returns remain in realized labels and can trigger the SHOCK regime.
- Slow WebSocket subscribers hold only the newest pending snapshot and cannot block forecasting.

## Reproducibility

All geometry uses integer ticks. Replay events and bootstrap seeds are deterministic. Dataset manifests include source semantics, time range, row count, missing rate, precision, and SHA-256. JSON/CSV exports retain frozen cell bounds. Parquet and DuckDB artifacts retain cell-level forecast/label rows for independent analysis.

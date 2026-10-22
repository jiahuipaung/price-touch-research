# TouchLab — price-interval touch probability

TouchLab is an auditable research application for estimating, every second, whether BTC, gold, or crude-oil prices will touch each price interval during each future time window. The default matrix is **21 price bands × 36 disjoint five-second windows**, starting at `+5s` and ending at `+185s`.

It is a research and calibration system, not a trading signal. Every snapshot includes frozen bounds, source state and age, raw/baseline/calibrated probabilities, model version, regime, path count, compute time, and quality flags.

## Three-minute acceptance

Requirements: Docker with Compose. No API key is needed after the image is built.

```bash
docker compose up --build -d
uv run python scripts/verify_runtime.py --base-url http://localhost:3000
```

Open [http://localhost:3000](http://localhost:3000). The checker waits for model readiness, verifies at least three advancing 21×36 snapshots, observes the deterministic `SOURCE_ERROR → HEALTHY` recovery, validates finite probabilities and a frozen-bounds CSV export, and confirms the UI is served.

In the UI:

1. **Live matrix** — select a cell and inspect its immutable price/time bounds and three probability variants. The fixed 0–100% color scale makes consecutive snapshots comparable.
2. **Research** — inspect Brier/log-loss/ECE evidence and the explicit `COMPACT_DEMO_NOT_FULL_CYCLE` disclosure.
3. **Data quality** — inspect counters and gap/reconnect behavior. A failed source is never silently replaced with a newly identified stale forecast.
4. **Methodology** — verify event semantics, assumptions, and limitations.

Stop the demo with `docker compose down`. The container runs as UID 10001 and exposes only port 3000.

### Live BTC mode

Use Binance Spot's public BTCUSDT trade stream instead of deterministic replay:

```bash
PRICE_TOUCH_DATA_MODE=LIVE docker compose up --build
```

No API key is required. Live ingestion and one-second matrix publication run as separate tasks, so a quiet
second still produces a newly estimated matrix from the latest eligible trade. Connection failures are exposed
as `SOURCE_ERROR`, retried with bounded exponential backoff, and return to `HEALTHY` only after a new trade is
received. The model initially reports `INSUFFICIENT_HISTORY` and `UNCALIBRATED` while the live history warms up.

Gold and oil remain explicitly delayed indicative sources; the application does not present them as five-second
tick-exact live feeds.

## Exact event

For forecast origin `t`, the price grid is frozen around the latest eligible price `Pₜ`. Price intervals and observation windows are half-open. A cell is 1 when **at least one eligible observed price at any instant in that window lies inside that interval**; closing inside is not required. Windows are disjoint, not cumulative. A discrete jump may skip an interval, so it does not fabricate a touch.

See [docs/methodology.md](docs/methodology.md) for formulas, models, calibration, exceptional conditions, and label precision.

## Local development and verification

```bash
uv sync --dev
cd frontend && npm ci && cd ..
make verify
```

`make verify` runs Python lint/tests, React tests, strict TypeScript checks, a production frontend build, the deterministic backtest, and the default 756-cell model benchmark. The fast backtest is intentionally synthetic and says so in its manifest; it proves reproducibility and plumbing, not market calibration.

Run the local single-port app after `make build`:

```bash
make dev
# http://localhost:8000
```

## Historical/full-cycle workflow

Full-cycle status is machine validated, not inferred from a chart. A valid report must cover LOW, MEDIUM, HIGH, and SHOCK regimes; span the declared coarse and high-resolution ranges; meet per-regime sample thresholds; and verify dataset checksums. Missing evidence produces `FULL_CYCLE_REQUIREMENTS_MISSING` and the absent requirement codes.

Acquire keyless public raw history:

```bash
uv run python scripts/download_history.py --asset BTC --start 2020-01-01 --end 2026-10-01 --output data/downloads/btc
```

For BTC the downloader converts public monthly one-minute OHLC archives directly into `market_events.csv` plus a checksum-backed `manifest.json`. These are real public observations with `BAR_APPROX` labels, not tick-exact trades. It also preserves every archive checksum and missing month in `download-manifest.json`. Because a multi-year download requires network access, it is not embedded in the repository or claimed as executed by `make verify`. Run the full-cycle gate with:

```bash
uv run python scripts/run_backtest.py --dataset data/downloads/btc/manifest.json --output artifacts/full-cycle-btc --minimum-samples-per-regime 50 --origin-cadence-seconds 86400
```

The report fails full-cycle validation unless all required regimes and temporal coverage are present. Gold and oil public quote endpoints are delayed/indicative; exact calibration requires separately licensed or public tick history. Approximate OHLC-derived labels must remain `BAR_APPROX` and are never mixed with `TICK_EXACT` headline results.

A checked-in summary of the freshly executed 2020 public-data run is available at [`docs/evidence/2020-btc-full-cycle-summary.json`](docs/evidence/2020-btc-full-cycle-summary.json). It covers 525,788 real one-minute bars and all four required regimes. The raw 26 MB of source ZIPs, 90 MB normalized CSV, Parquet, and DuckDB files remain reproducible but are not committed.

## Public sources

- BTC: Binance public BTCUSDT trade WebSocket (`LIVE`, no key).
- Gold: XAUS keyless indicative XAU/USD (`DELAYED`, not trade truth).
- Oil: AmericasOilWatch/Yahoo-derived WTI (`DELAYED`, not trade truth).
- Offline acceptance: clearly marked deterministic synthetic replay (`REPLAY`).

Run `uv run python scripts/probe_public_sources.py` only when network evidence is wanted. Failure is returned per source and never triggers silent replay fallback. Exact endpoints and semantics are in [docs/data-sources.md](docs/data-sources.md).

## Architecture

`adapter → quality gate → past-only features/regime → analytic + block-bootstrap model → past-only calibration → atomic snapshot store → HTTP/WebSocket/UI`

Matured forecasts are labeled against their own frozen geometry. Walk-forward processing is chronological; feature, regime, bootstrap, and calibration state never use future observations. Cell-level outputs are written to Parquet and DuckDB for independent queries.

## Known limitations

- The bundled dataset is a tiny deterministic fault fixture, not historical evidence and not full-cycle evidence.
- Free commodity endpoints are indicative and delayed; they cannot establish five-second tick-exact calibration.
- Bootstrap paths approximate future dynamics; extreme discontinuities and structural breaks remain uncertain.
- `BAR_APPROX` only knows the bar range, not the within-bar path.
- The runtime store is local/in-process and intended for one-node research acceptance, not distributed production serving.

The evidence checklist and expected outputs are in [docs/acceptance.md](docs/acceptance.md).

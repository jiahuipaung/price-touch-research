import type { ForecastSnapshot } from "./types";

export const fixtureSnapshot: ForecastSnapshot = {
  schema_version: "1.0",
  forecast_id: "BTC-100",
  asset: "BTC",
  instrument: "BTCUSDT",
  origin_time: "2026-10-21T08:00:00Z",
  published_at: "2026-10-21T08:00:00Z",
  origin_price_ticks: 6_700_000,
  intervals: [
    { index: -1, lower_ticks: 6_680_000, upper_ticks: 6_690_000 },
    { index: 0, lower_ticks: 6_690_000, upper_ticks: 6_700_000 },
    { index: 1, lower_ticks: 6_700_000, upper_ticks: 6_710_000 },
  ],
  windows: [
    { index: 0, start_ns: 100_000_000_000, end_ns: 105_000_000_000 },
    { index: 1, start_ns: 105_000_000_000, end_ns: 110_000_000_000 },
  ],
  matrices: {
    baseline: [[0.1, 0.12], [0.3, 0.35], [0.08, 0.1]],
    raw: [[0.11, 0.13], [0.32, 0.38], [0.09, 0.11]],
    calibrated: [[0.09, 0.12], [0.29, 0.34], [0.07, 0.09]],
  },
  source: {
    mode: "REPLAY",
    provider: "deterministic demo",
    age_seconds: 1.25,
    last_event_time: "2026-10-21T07:59:59Z",
    stale: false,
    market_closed: false,
    message: "HEALTHY",
  },
  model_version: "bootstrap-v1",
  regime: "MEDIUM",
  path_count: 2_000,
  compute_duration_ms: 13.4,
  quality_flags: ["UNCALIBRATED"],
};

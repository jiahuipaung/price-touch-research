export type SourceMode = "LIVE" | "DELAYED" | "REPLAY" | "DEGRADED";

export type QualityFlag =
  | "UNCALIBRATED"
  | "INSUFFICIENT_HISTORY"
  | "STALE"
  | "MARKET_CLOSED"
  | "REDUCED_PATHS"
  | "ANALYTIC_FALLBACK"
  | "BAR_APPROX";

export interface IntervalBounds {
  index: number;
  lower_ticks: number;
  upper_ticks: number;
}

export interface WindowBounds {
  index: number;
  start_ns: number;
  end_ns: number;
}

export interface SourceStatus {
  mode: SourceMode;
  provider: string;
  age_seconds: number;
  last_event_time: string | null;
  stale: boolean;
  market_closed: boolean;
  message: string | null;
}

export interface MatrixPayload {
  baseline: number[][];
  raw: number[][];
  calibrated: number[][];
}

export interface ForecastSnapshot {
  schema_version: string;
  forecast_id: string;
  asset: string;
  instrument: string;
  origin_time: string;
  published_at: string;
  origin_price_ticks: number;
  intervals: IntervalBounds[];
  windows: WindowBounds[];
  matrices: MatrixPayload;
  source: SourceStatus;
  model_version: string;
  regime: string;
  path_count: number;
  compute_duration_ms: number;
  quality_flags: QualityFlag[];
}

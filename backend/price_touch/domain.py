from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class SourceMode(StrEnum):
    LIVE = "LIVE"
    DELAYED = "DELAYED"
    REPLAY = "REPLAY"
    DEGRADED = "DEGRADED"


class QualityFlag(StrEnum):
    UNCALIBRATED = "UNCALIBRATED"
    INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
    STALE = "STALE"
    MARKET_CLOSED = "MARKET_CLOSED"
    REDUCED_PATHS = "REDUCED_PATHS"
    ANALYTIC_FALLBACK = "ANALYTIC_FALLBACK"
    BAR_APPROX = "BAR_APPROX"


class EventKind(StrEnum):
    TRADE = "TRADE"
    BAR = "BAR"


class MarketEvent(BaseModel):
    asset: str
    instrument: str
    event_time: datetime
    received_time: datetime
    price_ticks: int
    trade_id: str
    kind: EventKind = EventKind.TRADE
    low_ticks: int | None = None
    high_ticks: int | None = None


class SourceStatus(BaseModel):
    mode: SourceMode
    provider: str
    age_seconds: float = Field(ge=0)
    last_event_time: datetime | None
    stale: bool
    market_closed: bool
    message: str | None = None


class IntervalBounds(BaseModel):
    index: int
    lower_ticks: int
    upper_ticks: int

    @model_validator(mode="after")
    def upper_exceeds_lower(self) -> "IntervalBounds":
        if self.upper_ticks <= self.lower_ticks:
            raise ValueError("upper_ticks must exceed lower_ticks")
        return self


class WindowBounds(BaseModel):
    index: int
    start_ns: int
    end_ns: int

    @model_validator(mode="after")
    def end_exceeds_start(self) -> "WindowBounds":
        if self.end_ns <= self.start_ns:
            raise ValueError("end_ns must exceed start_ns")
        return self


class ForecastGeometry(BaseModel):
    origin_ns: int
    origin_price_ticks: int = Field(gt=0)
    intervals: list[IntervalBounds]
    windows: list[WindowBounds]


class MatrixPayload(BaseModel):
    baseline: list[list[float]]
    raw: list[list[float]]
    calibrated: list[list[float]]

    @model_validator(mode="after")
    def matrices_have_one_shape(self) -> "MatrixPayload":
        shapes = {
            (len(matrix), len(matrix[0]) if matrix else 0)
            for matrix in (self.baseline, self.raw, self.calibrated)
        }
        if len(shapes) != 1 or any(len(row) != next(iter(shapes))[1] for matrix in (self.baseline, self.raw, self.calibrated) for row in matrix):
            raise ValueError("all probability matrices must be rectangular and share one shape")
        for matrix in (self.baseline, self.raw, self.calibrated):
            if any(not 0 <= value <= 1 for row in matrix for value in row):
                raise ValueError("probabilities must be between zero and one")
        return self


class ForecastSnapshot(BaseModel):
    schema_version: str
    forecast_id: str
    asset: str
    instrument: str
    origin_time: datetime
    published_at: datetime
    origin_price_ticks: int = Field(gt=0)
    intervals: list[IntervalBounds]
    windows: list[WindowBounds]
    matrices: MatrixPayload
    source: SourceStatus
    model_version: str
    regime: str
    path_count: int = Field(ge=0)
    compute_duration_ms: float = Field(ge=0)
    quality_flags: list[QualityFlag] = Field(default_factory=list)

    @model_validator(mode="after")
    def matrix_matches_frozen_geometry(self) -> "ForecastSnapshot":
        expected = (len(self.intervals), len(self.windows))
        actual = (
            len(self.matrices.calibrated),
            len(self.matrices.calibrated[0]) if self.matrices.calibrated else 0,
        )
        if actual != expected:
            raise ValueError(f"matrix shape {actual} does not match geometry {expected}")
        return self

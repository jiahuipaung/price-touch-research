from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, HttpUrl, model_validator

from price_touch.labeling import LabelPrecision


class SourceKind(StrEnum):
    REAL_PUBLIC = "REAL_PUBLIC"
    DETERMINISTIC_SYNTHETIC = "DETERMINISTIC_SYNTHETIC"


class DemoManifest(BaseModel):
    asset: str
    instrument: str
    source_kind: SourceKind
    source_url: HttpUrl | None
    acquired_at: datetime
    start_time: datetime
    end_time: datetime
    resolution: str = Field(min_length=1)
    label_precision: LabelPrecision
    row_count: int = Field(gt=0)
    missing_rate: float = Field(ge=0, le=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    file: str = Field(min_length=1)
    fault_scenarios_file: str | None = None

    @model_validator(mode="after")
    def time_range_is_ordered(self) -> "DemoManifest":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, PositiveInt, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AssetConfig(BaseModel):
    symbol: str
    instrument: str
    tick_size: Decimal = Field(gt=0)
    step_ticks: PositiveInt


class MatrixConfig(BaseModel):
    interval_count: int = Field(default=21, ge=3, le=199)
    window_count: int = Field(default=36, ge=1, le=120)
    observation_delay_seconds: int = Field(default=5, ge=1, le=300)
    window_seconds: int = Field(default=5, ge=1, le=300)

    @field_validator("interval_count")
    @classmethod
    def require_odd_interval_count(cls, value: int) -> int:
        if value % 2 == 0:
            raise ValueError("interval_count must be odd so one interval is centered on the origin")
        return value


def default_assets() -> dict[str, AssetConfig]:
    return {
        "BTC": AssetConfig(symbol="BTC", instrument="BTCUSDT", tick_size=Decimal("0.01"), step_ticks=2_000),
        "GOLD": AssetConfig(symbol="GOLD", instrument="XAUUSD", tick_size=Decimal("0.01"), step_ticks=200),
        "OIL": AssetConfig(symbol="OIL", instrument="WTIUSD", tick_size=Decimal("0.001"), step_ticks=250),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PRICE_TOUCH_", env_nested_delimiter="__")

    matrix: MatrixConfig = Field(default_factory=MatrixConfig)
    assets: dict[str, AssetConfig] = Field(default_factory=default_assets)
    publication_interval_seconds: int = Field(default=1, ge=1, le=60)
    monte_carlo_paths: int = Field(default=2_000, ge=100, le=100_000)
    data_mode: str = "REPLAY"
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65_535)

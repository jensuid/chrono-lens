"""Pydantic request models for the analysis endpoints.

Field names are camelCase on the wire (the frontend convention); pydantic
models use snake_case internally with populate_by_name so both spellings
are accepted.
"""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CamelModel(BaseModel):
    """Base model accepting camelCase wire names for snake_case fields."""

    model_config = ConfigDict(populate_by_name=True)


class StatsRequest(CamelModel):
    """Descriptive statistics for one numeric column."""

    column: str


class ResampleRequest(CamelModel):
    """Aggregate the series onto a new frequency grid."""

    column: str
    # UI frequency enum (mapped to pandas aliases server-side).
    freq: str = Field(pattern="^(H|D|W|M|Q)$")
    agg: str = Field(pattern="^(mean|sum|max|min)$")


class RollingRequest(CamelModel):
    """Rolling window statistic over one numeric column."""

    column: str
    window: int = Field(gt=1, le=10000)
    stat: str = Field(pattern="^(mean|std|min|max)$")


class DecomposeRequest(CamelModel):
    """Seasonal/trend decomposition of one numeric column."""

    column: str
    period: int = Field(ge=2, le=100000)
    method: str = Field(pattern="^(stl|classical)$")


class StationarityRequest(CamelModel):
    """ADF and KPSS stationarity tests for one numeric column."""

    column: str


class AcfRequest(CamelModel):
    """ACF/PACF values with confidence bands for one numeric column."""

    column: str
    nlags: int = Field(ge=1, le=500)


class ForecastSarimaRequest(CamelModel):
    """SARIMA (p, d, q) x (P, D, Q, s) model configuration."""

    column: str
    horizon: int = Field(ge=1, le=365)
    train_ratio: float = Field(gt=0.5, le=1.0, alias="trainRatio")
    order: list[int] = Field(min_length=3, max_length=3)
    seasonal_order: Optional[list[int]] = Field(
        default=None, min_length=4, max_length=4, alias="seasonalOrder"
    )


class ForecastHwRequest(CamelModel):
    """Holt-Winters exponential smoothing configuration."""

    column: str
    horizon: int = Field(ge=1, le=365)
    train_ratio: float = Field(gt=0.5, le=1.0, alias="trainRatio")
    trend: str = Field(pattern="^(add|mul|None)$")
    seasonal: str = Field(pattern="^(add|mul|None)$")
    seasonal_periods: Optional[int] = Field(
        default=None, ge=2, le=1000, alias="seasonalPeriods"
    )


class AnomaliesRequest(CamelModel):
    """Anomaly screening for one numeric column."""

    column: str
    method: str = Field(pattern="^(zscore|iqr|stl)$")
    threshold: float = Field(gt=0)
    window: int = Field(default=20, ge=3, le=10000)
    period: Optional[int] = Field(default=None, ge=2, le=100000)

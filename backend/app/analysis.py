"""Explore endpoints: descriptive stats, resampling, rolling windows."""

import numpy as np
import pandas as pd
from fastapi import APIRouter

from .datasets import _rows
from .errors import bad_request
from .schemas import ResampleRequest, RollingRequest, StatsRequest
from .store import Dataset

router = APIRouter(prefix="/api/datasets", tags=["explore"])


def _value_frame(ds: Dataset, column: str) -> pd.DataFrame:
    """Frame with datetime index and the requested numeric column.

    Raises 400 UNKNOWN_COLUMN when the column is absent, 400
    NOT_NUMERIC when it cannot serve as an analysis value.
    """
    frame = ds.frame
    if column not in frame.columns:
        raise bad_request(
            "UNKNOWN_COLUMN",
            f"column {column!r} does not exist",
            {"available": [str(c) for c in frame.columns]},
        )
    if not pd.api.types.is_numeric_dtype(frame[column]):
        raise bad_request(
            "NOT_NUMERIC", f"column {column!r} is not numeric"
        )
    time_col = None
    for c in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[c]):
            time_col = c
            break
    indexed = frame[[time_col, column]].copy()
    indexed = indexed.set_index(time_col).sort_index()
    return indexed


@router.post("/{dataset_id}/stats")
async def stats(dataset_id: str, req: StatsRequest):
    """Descriptive statistics for one numeric column."""
    ds = Dataset.load(dataset_id)
    series = _value_frame(ds, req.column)[req.column]
    stats = {
        "count": int(series.count()),
        "mean": float(series.mean()),
        "std": float(series.std()),
        "min": float(series.min()),
        "q25": float(series.quantile(0.25)),
        "median": float(series.median()),
        "q75": float(series.quantile(0.75)),
        "max": float(series.max()),
    }
    out = {"stats": stats, "missing": int(series.isna().sum())}
    return out


# UI frequency enum -> modern pandas offset alias (M is deprecated).
_FREQ_ALIASES = {"H": "h", "D": "D", "W": "W", "M": "ME", "Q": "QE"}


@router.post("/{dataset_id}/resample")
async def resample(dataset_id: str, req: ResampleRequest):
    """Aggregate the series onto a coarser frequency grid."""
    ds = Dataset.load(dataset_id)
    indexed = _value_frame(ds, req.column)
    agg = getattr(indexed.resample(_FREQ_ALIASES[req.freq]), req.agg)
    result = agg()
    # resample().agg() on a one-column frame returns a DataFrame; squeeze
    # to a Series so _series_points iterates (timestamp, value) pairs.
    series = result.squeeze(axis=1) if isinstance(result, pd.DataFrame) else result
    return {
        "column": req.column,
        "freq": req.freq,
        "agg": req.agg,
        "points": _series_points(series),
    }


@router.post("/{dataset_id}/rolling")
async def rolling(dataset_id: str, req: RollingRequest):
    """Rolling window statistic with min_periods=window (honest edges)."""
    ds = Dataset.load(dataset_id)
    series = _value_frame(ds, req.column)[req.column]
    if req.window > len(series):
        raise bad_request(
            "WINDOW_TOO_LARGE",
            f"window {req.window} exceeds series length {len(series)}",
        )
    roller = series.rolling(window=req.window, min_periods=req.window)
    stat = getattr(roller, req.stat)()
    return {
        "column": req.column,
        "window": req.window,
        "stat": req.stat,
        "points": _series_points(stat),
    }


def _series_points(series: pd.Series) -> list[dict]:
    """(timestamp_ms, value-or-null) pairs from an indexed series."""
    out = []
    for ts, value in series.items():
        ms = int(pd.Timestamp(ts).value // 1_000_000)
        out.append(
            {"t": ms, "v": None if pd.isna(value) else float(value)}
        )
    return out


def to_records(frame: pd.DataFrame) -> list[dict]:
    """Public re-export so other modules reuse the row cleaner."""
    return _rows(frame)


def series_of(indexed: pd.DataFrame, column: str) -> pd.Series:
    """The value column of an indexed frame with NaNs preserved."""
    return indexed[column]

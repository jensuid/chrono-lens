"""Anomaly detection: rolling z-score, IQR, STL residual."""

import numpy as np
import pandas as pd
from fastapi import APIRouter
from statsmodels.tsa.seasonal import STL

from .analysis import _value_frame
from .errors import bad_request
from .schemas import AnomaliesRequest
from .store import Dataset

router = APIRouter(prefix="/api/datasets", tags=["anomalies"])


def _base_series(ds: Dataset, column: str) -> pd.Series:
    """Datetime-indexed value series (missing values preserved)."""
    return _value_frame(ds, column)[column]


def _mark(
    series: pd.Series, flags: pd.Series, method: str, detail: dict
) -> dict:
    """Uniform anomaly listing from a boolean flag series."""
    out = []
    for ts, value, flagged in zip(
        series.index, series.values, flags.values, strict=True
    ):
        if flagged:
            out.append(
                {
                    "t": int(pd.Timestamp(ts).value // 1_000_000),
                    "v": None if pd.isna(value) else float(value),
                }
            )
    return {"method": method, **detail, "anomalies": out}


@router.post("/{dataset_id}/anomalies")
async def detect(dataset_id: str, req: AnomaliesRequest):
    """Screen one numeric column with the chosen method."""
    ds = Dataset.load(dataset_id)
    series = _base_series(ds, req.column)

    if req.method == "zscore":
        if req.window > len(series):
            raise bad_request(
                "WINDOW_TOO_LARGE",
                f"window {req.window} exceeds series length {len(series)}",
            )
        # Prior-window statistics exclude the point under test: a window
        # containing the candidate spike inflates its own mean/std and
        # dilutes the z-score (a +45 spike on sigma=3 noise scores only
        # ~3.2 with an including window).
        mean = series.rolling(req.window, min_periods=req.window).mean().shift(1)
        std = series.rolling(req.window, min_periods=req.window).std().shift(1)
        zscore = (series - mean) / std
        flags = zscore.abs() > req.threshold
        return _mark(
            series,
            flags,
            "zscore",
            {"window": req.window, "threshold": req.threshold},
        )

    if req.method == "iqr":
        q1 = float(series.quantile(0.25))
        q3 = float(series.quantile(0.75))
        iqr = q3 - q1
        # threshold scales the IQR fence distance (1.5 = classic Tukey).
        k = req.threshold if req.threshold != 0 else 1.5
        low, high = q1 - k * iqr, q3 + k * iqr
        flags = (series < low) | (series > high)
        return _mark(
            series,
            flags,
            "iqr",
            {"fenceLow": low, "fenceHigh": high, "threshold": req.threshold},
        )

    # method == "stl": flag large residuals from a seasonal decomposition.
    period = req.period
    if period is None:
        raise bad_request(
            "MISSING_PERIOD", "STL anomaly detection needs a period"
        )
    if period > len(series) // 2:
        raise bad_request(
            "INVALID_PERIOD",
            f"period {period} too large for {len(series)} points",
        )
    complete = series.interpolate(method="time").dropna()
    fit = STL(complete, period=period).fit()
    resid = fit.resid
    mu, sigma = float(resid.mean()), float(resid.std())
    flags = (resid - mu).abs() > req.threshold * sigma
    flagged_times = set(flags[flags].index)
    # Map back onto the original (possibly gapped) series.
    original_flags = pd.Series(False, index=series.index)
    original_flags[original_flags.index.isin(flagged_times)] = True
    return _mark(
        series,
        original_flags,
        "stl",
        {"period": period, "threshold": req.threshold},
    )

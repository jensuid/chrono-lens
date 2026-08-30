"""Decomposition and diagnosis: STL/classical, ADF/KPSS, ACF/PACF."""

import numpy as np
import pandas as pd
from fastapi import APIRouter
from statsmodels.tsa.seasonal import STL, seasonal_decompose
from statsmodels.tsa.stattools import acf, adfuller, kpss, pacf

from .analysis import _series_points, _value_frame
from .errors import bad_request
from .schemas import AcfRequest, DecomposeRequest, StationarityRequest
from .store import Dataset

router = APIRouter(prefix="/api/datasets", tags=["decompose"])


def _clean_series(ds: Dataset, column: str) -> pd.Series:
    """The value series, datetime-indexed, missing values interpolated.

    Decomposition and ACF/PACF need complete series: interior gaps are
    linearly interpolated (documented in the response so the UI can show
    it); series with no observations left raise 400.
    """
    indexed = _value_frame(ds, column)
    series = indexed[column].interpolate(method="time").dropna()
    if len(series) < 2 * 7:
        raise bad_request(
            "INSUFFICIENT_DATA",
            f"series has {len(series)} usable points; decomposition "
            "needs at least 14",
        )
    return series


@router.post("/{dataset_id}/decompose")
async def decompose(dataset_id: str, req: DecomposeRequest):
    """Observed/trend/seasonal/residual components."""
    ds = Dataset.load(dataset_id)
    series = _clean_series(ds, req.column)
    if req.period > len(series) // 2:
        raise bad_request(
            "INVALID_PERIOD",
            f"period {req.period} too large for {len(series)} points "
            "(needs at least 2 full cycles)",
        )
    if req.method == "stl":
        fit = STL(series, period=req.period).fit()
        trend, seasonal, resid = fit.trend, fit.seasonal, fit.resid
    else:
        fit = seasonal_decompose(series, period=req.period)
        trend, seasonal, resid = fit.trend, fit.seasonal, fit.resid
    return {
        "method": req.method,
        "period": req.period,
        "observed": _series_points(series),
        "trend": _series_points(trend),
        "seasonal": _series_points(seasonal),
        "residual": _series_points(resid),
    }


@router.post("/{dataset_id}/stationarity")
async def stationarity(dataset_id: str, req: StationarityRequest):
    """ADF and KPSS tests with interpretations."""
    ds = Dataset.load(dataset_id)
    series = _clean_series(ds, req.column)

    # adfuller(autolag) returns (stat, pvalue, usedlag, nobs, crit, icbest).
    adf_result = adfuller(series, autolag="AIC")
    adf_stat, adf_p = float(adf_result[0]), float(adf_result[1])
    adf_crit = adf_result[4]
    # KPSS warning suppression: statsmodels prints an InterpolationWarning
    # when the statistic falls outside the tabulated critical range.
    import warnings

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        kpss_stat, kpss_p, _, kpss_crit = kpss(series, regression="c", nlags="auto")

    def _interpret_adf(p: float) -> str:
        if p < 0.05:
            return "p < 0.05: reject the unit-root null; series is stationary"
        return "p >= 0.05: fail to reject the unit root; series looks non-stationary"

    def _interpret_kpss(p: float) -> str:
        if p < 0.05:
            return "p < 0.05: reject the stationary null; series looks non-stationary"
        return "p >= 0.05: fail to reject the stationary null; series is stationary"

    return {
        "adf": {
            "statistic": float(adf_stat),
            "pvalue": float(adf_p),
            "criticalValues": {k: float(v) for k, v in adf_crit.items()},
            "interpretation": _interpret_adf(float(adf_p)),
        },
        "kpss": {
            "statistic": float(kpss_stat),
            "pvalue": float(kpss_p),
            "criticalValues": {k: float(v) for k, v in kpss_crit.items()},
            "interpretation": _interpret_kpss(float(kpss_p)),
        },
    }


@router.post("/{dataset_id}/acf")
async def acf_pacf(dataset_id: str, req: AcfRequest):
    """ACF and PACF values with 95% confidence bands."""
    ds = Dataset.load(dataset_id)
    series = _clean_series(ds, req.column)
    if req.nlags >= len(series):
        raise bad_request(
            "INVALID_NLAGS",
            f"nlags {req.nlags} must be below the series length {len(series)}",
        )
    acf_values = acf(series, nlags=req.nlags, fft=True)
    pacf_values = pacf(series, nlags=req.nlags)
    band = 1.96 / np.sqrt(len(series))
    return {
        "nlags": req.nlags,
        "band": float(band),
        "acf": [float(v) for v in acf_values],
        "pacf": [float(v) for v in pacf_values],
    }

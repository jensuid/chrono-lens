"""Forecast endpoints: SARIMA and Holt-Winters with backtest metrics."""

import numpy as np
import pandas as pd
from fastapi import APIRouter
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from .analysis import _series_points, _value_frame
from .errors import bad_request
from .schemas import ForecastHwRequest, ForecastSarimaRequest
from .store import Dataset

router = APIRouter(prefix="/api/datasets", tags=["forecast"])


def _infer_freq(series: pd.Series) -> str:
    """Best-effort cadence: pandas inference, then median spacing."""
    try:
        return pd.infer_freq(series.index) or "D"
    except (ValueError, TypeError):
        pass
    diffs = series.index.to_series().diff().dropna()
    if diffs.empty:
        return "D"
    seconds = int(diffs.dt.total_seconds().median())
    for stride, alias in (
        (604800, "W"),
        (86400, "D"),
        (3600, "h"),
        (60, "min"),
    ):
        if seconds >= stride:
            return alias
    return "D"


def _prepare(ds: Dataset, column: str) -> pd.Series:
    """Interpolated, dropna'd value series (forecast models need complete data)."""
    indexed = _value_frame(ds, column)
    series = indexed[column].interpolate(method="time").dropna()
    if len(series) < 30:
        raise bad_request(
            "INSUFFICIENT_DATA",
            f"series has {len(series)} usable points; forecasting needs at least 30",
        )
    return series


def _split(series: pd.Series, train_ratio: float):
    """Train/test split preserving order; test must be non-empty."""
    cut = int(len(series) * train_ratio)
    if cut >= len(series) or cut < 10:
        raise bad_request(
            "INVALID_SPLIT",
            f"train ratio {train_ratio} leaves an unusable split "
            f"({cut} train of {len(series)})",
        )
    return series.iloc[:cut], series.iloc[cut:]


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict:
    """MAE / RMSE / MAPE on the backtest holdout."""
    error = actual - predicted
    mae = float(np.mean(np.abs(error)))
    rmse = float(np.sqrt(np.mean(error**2)))
    nonzero = actual != 0
    mape = (
        float(np.mean(np.abs(error[nonzero]) / np.abs(actual[nonzero])) * 100)
        if nonzero.any()
        else None
    )
    return {"mae": mae, "rmse": rmse, "mape": mape}


@router.post("/{dataset_id}/forecast/sarima")
async def forecast_sarima(dataset_id: str, req: ForecastSarimaRequest):
    """SARIMA (p, d, q) x (P, D, Q, s) with train/test backtest."""
    ds = Dataset.load(dataset_id)
    series = _prepare(ds, req.column)
    train, test = _split(series, req.train_ratio)

    seasonal = None
    if req.seasonal_order is not None:
        seasonal = tuple(req.seasonal_order)

    try:
        model = SARIMAX(
            train,
            order=tuple(req.order),
            seasonal_order=seasonal,
            enforce_stationarity=False,
            enforce_invertibility=False,
        ).fit(disp=False)
    except Exception as exc:  # noqa: BLE001 - statsmodels raises many shapes
        raise bad_request(
            "MODEL_FIT_ERROR", f"SARIMA fit failed: {exc}", str(type(exc).__name__)
        ) from exc

    # In-sample fitted values over the test horizon.
    n_forecast = len(test) + req.horizon
    forecast = model.get_forecast(steps=n_forecast)
    predicted = np.asarray(forecast.predicted_mean)[: len(test)]
    ci = np.asarray(forecast.conf_int(alpha=0.05))
    lo_test, hi_test = ci[: len(test), 0], ci[: len(test), 1]
    lo_horizon, hi_horizon = (
        (ci[len(test):, 0], ci[len(test):, 1])
        if len(test) < n_forecast
        else ([], [])
    )

    metrics = _metrics(np.asarray(test), predicted)

    # Infer the cadence for the horizon index; fall back to the median
    # spacing when the index carries no freq (gaps from missing values).
    freq = series.index.freq or _infer_freq(series)
    horizon_index = pd.date_range(
        test.index[-1], periods=req.horizon + 1, freq=freq
    )[1:]
    horizon_values = np.asarray(forecast.predicted_mean)[len(test):]

    return {
        "model": "sarima",
        "order": req.order,
        "seasonalOrder": req.seasonal_order,
        "train": _series_points(train),
        "test": _series_points(test),
        "fitted": _series_points(
            pd.Series(predicted, index=test.index)
        ),
        "forecast": {
            "points": [
                {"t": int(ts.value // 1_000_000), "v": float(v)}
                for ts, v in zip(horizon_index, horizon_values, strict=False)
            ],
            "low": [
                {"t": int(ts.value // 1_000_000), "v": float(v)}
                for ts, v in zip(horizon_index, lo_horizon, strict=False)
            ],
            "high": [
                {"t": int(ts.value // 1_000_000), "v": float(v)}
                for ts, v in zip(horizon_index, hi_horizon, strict=False)
            ],
        },
        "metrics": metrics,
        "testBand": {
            "low": [
                {"t": int(ts.value // 1_000_000), "v": float(v)}
                for ts, v in zip(test.index, lo_test, strict=False)
            ],
            "high": [
                {"t": int(ts.value // 1_000_000), "v": float(v)}
                for ts, v in zip(test.index, hi_test, strict=False)
            ],
        },
    }


@router.post("/{dataset_id}/forecast/hw")
async def forecast_hw(dataset_id: str, req: ForecastHwRequest):
    """Holt-Winters exponential smoothing with backtest."""
    ds = Dataset.load(dataset_id)
    series = _prepare(ds, req.column)
    train, test = _split(series, req.train_ratio)

    trend = None if req.trend == "None" else req.trend
    seasonal = None if req.seasonal == "None" else req.seasonal
    if seasonal is not None and req.seasonal_periods is None:
        raise bad_request(
            "MISSING_SEASONAL_PERIODS",
            "seasonal Holt-Winters needs seasonal_periods",
        )

    try:
        model = ExponentialSmoothing(
            train,
            trend=trend,
            seasonal=seasonal,
            seasonal_periods=req.seasonal_periods,
        ).fit()
    except Exception as exc:  # noqa: BLE001
        raise bad_request(
            "MODEL_FIT_ERROR", f"Holt-Winters fit failed: {exc}", str(type(exc).__name__)
        ) from exc

    n_forecast = len(test) + req.horizon
    predicted = np.asarray(model.forecast(n_forecast))
    pred_test = predicted[: len(test)]
    pred_horizon = predicted[len(test):]

    metrics = _metrics(np.asarray(test), pred_test)

    freq = series.index.freq or _infer_freq(series)
    horizon_index = pd.date_range(
        test.index[-1], periods=req.horizon + 1, freq=freq
    )[1:]

    return {
        "model": "hw",
        "trend": req.trend,
        "seasonal": req.seasonal,
        "seasonalPeriods": req.seasonal_periods,
        "train": _series_points(train),
        "test": _series_points(test),
        "fitted": _series_points(pd.Series(pred_test, index=test.index)),
        "forecast": {
            "points": [
                {"t": int(ts.value // 1_000_000), "v": float(v)}
                for ts, v in zip(horizon_index, pred_horizon, strict=False)
            ],
            # ExponentialSmoothing has no closed-form CI; the UI shades
            # nothing extra for HW.
            "low": [],
            "high": [],
        },
        "metrics": metrics,
        "testBand": {"low": [], "high": []},
    }

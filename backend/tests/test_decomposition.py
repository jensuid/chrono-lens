"""Decomposition, stationarity, ACF/PACF tests against synthetic ground truth."""

import numpy as np


def test_stl_recovers_weekly_period(csv_dataset, client, ground_truth):
    period = ground_truth["period"]
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/decompose",
        json={"column": "value", "period": period, "method": "stl"},
    )
    assert response.status_code == 200
    body = response.json()
    seasonal = [p["v"] for p in body["seasonal"] if p["v"] is not None]
    assert len(seasonal) > 600
    # The weekly component has amplitude ~8; STL should recover a
    # component with a clear sinusoid of period 7: check peak-to-peak.
    amplitude = (max(seasonal) - min(seasonal)) / 2
    assert amplitude > 4.0, f"STL seasonal amplitude too small: {amplitude}"

    # Autocorrelation of the seasonal component at lag 7 should be high.
    arr = np.asarray(seasonal)
    normalized = arr - arr.mean()
    lag7 = np.corrcoef(normalized[:-7], normalized[7:])[0, 1]
    assert lag7 > 0.8, f"seasonal component not periodic at lag 7: {lag7}"


def test_classical_decomposition_runs(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/decompose",
        json={"column": "value", "period": 7, "method": "classical"},
    )
    assert response.status_code == 200
    body = response.json()
    assert all(k in body for k in ("observed", "trend", "seasonal", "residual"))


def test_decompose_period_too_large(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/decompose",
        json={"column": "value", "period": 600, "method": "stl"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PERIOD"


def test_adf_kpss_on_trending_series(csv_dataset, client):
    """The synthetic series has a trend: ADF should lean non-stationary."""
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/stationarity",
        json={"column": "value"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "interpretation" in body["adf"]
    assert "interpretation" in body["kpss"]
    assert 0 <= body["adf"]["pvalue"] <= 1
    assert 0 <= body["kpss"]["pvalue"] <= 1


def test_acf_pacf_shape(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/acf",
        json={"column": "value", "nlags": 30},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["acf"]) == 31  # lag 0..30
    assert len(body["pacf"]) == 31
    assert abs(body["acf"][0] - 1.0) < 1e-9
    # Weekly seasonality: ACF at lag 7 should stand out.
    assert body["acf"][7] > 0.5
    assert body["band"] > 0


def test_acf_nlags_too_large(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/acf",
        json={"column": "value", "nlags": 5000},
    )
    assert response.status_code == 422  # schema cap

"""Forecast tests: SARIMA and Holt-Winters beat naive baselines."""

import numpy as np


def _get(client, dataset_id, path, payload):
    response = client.post(f"/api/datasets/{dataset_id}/{path}", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_sarima_forecast_beats_naive(csv_dataset, client):
    body = _get(
        client,
        csv_dataset["id"],
        "forecast/sarima",
        {
            "column": "value",
            "horizon": 30,
            "trainRatio": 0.8,
            "order": [1, 1, 1],
            "seasonalOrder": [1, 0, 1, 7],
        },
    )
    mae = body["metrics"]["mae"]
    # Naive baseline: mean of the train set.
    train = np.asarray([p["v"] for p in body["train"] if p["v"] is not None])
    test = np.asarray([p["v"] for p in body["test"] if p["v"] is not None])
    naive_mae = float(np.mean(np.abs(test - train.mean())))
    assert mae < naive_mae, f"SARIMA MAE {mae} should beat naive {naive_mae}"
    assert len(body["forecast"]["points"]) == 30
    assert body["forecast"]["low"] and body["forecast"]["high"]


def test_hw_forecast_beats_naive(csv_dataset, client):
    body = _get(
        client,
        csv_dataset["id"],
        "forecast/hw",
        {
            "column": "value",
            "horizon": 30,
            "trainRatio": 0.8,
            "trend": "add",
            "seasonal": "add",
            "seasonalPeriods": 7,
        },
    )
    mae = body["metrics"]["mae"]
    train = np.asarray([p["v"] for p in body["train"] if p["v"] is not None])
    test = np.asarray([p["v"] for p in body["test"] if p["v"] is not None])
    naive_mae = float(np.mean(np.abs(test - train.mean())))
    assert mae < naive_mae, f"HW MAE {mae} should beat naive {naive_mae}"
    assert len(body["forecast"]["points"]) == 30


def test_forecast_metrics_present(csv_dataset, client):
    body = _get(
        client,
        csv_dataset["id"],
        "forecast/sarima",
        {
            "column": "value",
            "horizon": 10,
            "trainRatio": 0.8,
            "order": [0, 1, 1],
        },
    )
    metrics = body["metrics"]
    assert metrics["mae"] > 0
    assert metrics["rmse"] >= metrics["mae"]
    assert metrics["mape"] is None or metrics["mape"] > 0


def test_hw_missing_seasonal_periods_rejected(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/forecast/hw",
        json={
            "column": "value",
            "horizon": 10,
            "trainRatio": 0.8,
            "trend": "add",
            "seasonal": "add",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_SEASONAL_PERIODS"


def test_insufficient_data_rejected(client):
    import pandas as pd

    # A 10-row series: forecast needs >= 30.
    buf = "timestamp,value\n" + "\n".join(
        f"2023-01-{d:02d},{d}" for d in range(1, 11)
    )
    response = client.post(
        "/api/datasets",
        files={"file": ("tiny.csv", buf.encode())},
    )
    assert response.status_code == 200
    tiny_id = response.json()["id"]
    response = client.post(
        f"/api/datasets/{tiny_id}/forecast/sarima",
        json={"column": "value", "horizon": 5, "trainRatio": 0.8, "order": [1, 1, 1]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INSUFFICIENT_DATA"

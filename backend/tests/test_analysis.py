"""Explore endpoints: stats, resample, rolling."""

import math


def test_stats(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/stats",
        json={"column": "value"},
    )
    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["count"] == 730 - 15  # missing values removed
    assert 95 < stats["mean"] < 155
    assert stats["min"] < stats["q25"] < stats["median"] < stats["q75"] < stats["max"]


def test_stats_unknown_column(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/stats",
        json={"column": "nope"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_COLUMN"


def test_resample_monthly_mean(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/resample",
        json={"column": "value", "freq": "M", "agg": "mean"},
    )
    assert response.status_code == 200
    body = response.json()
    # 730 days ~ 24 months
    assert 23 <= len(body["points"]) <= 25
    # Monthly means sit near the daily level (~100-140)
    values = [p["v"] for p in body["points"] if p["v"] is not None]
    assert values and all(90 < v < 160 for v in values)


def test_resample_invalid_freq(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/resample",
        json={"column": "value", "freq": "Z", "agg": "mean"},
    )
    # Pydantic pattern rejection -> FastAPI 422 with its own shape.
    assert response.status_code == 422


def test_rolling_mean_smoothes(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/rolling",
        json={"column": "value", "window": 7, "stat": "mean"},
    )
    assert response.status_code == 200
    points = response.json()["points"]
    # min_periods=window: the first 6 are null
    assert all(p["v"] is None for p in points[:6])
    assert points[6]["v"] is not None


def test_rolling_window_too_large(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/rolling",
        json={"column": "value", "window": 99999, "stat": "mean"},
    )
    assert response.status_code == 422  # schema cap is 10000

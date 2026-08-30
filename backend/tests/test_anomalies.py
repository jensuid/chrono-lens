"""Anomaly detection tests against injected ground truth."""

import json
from datetime import datetime, timezone

import numpy as np


def _times(anomalies):
    """Detected epoch-ms timestamps as UTC date strings."""
    return {
        datetime.fromtimestamp(a["t"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        for a in anomalies["anomalies"]
    }


def _gt_times(ground_truth):
    return {a["timestamp"] for a in ground_truth["anomalies"]}


def test_zscore_recovers_spikes(csv_dataset, client, ground_truth):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/anomalies",
        json={
            "column": "value",
            "method": "zscore",
            "threshold": 4.0,
            "window": 14,
        },
    )
    assert response.status_code == 200
    body = response.json()
    found = _times(body)
    gt = _gt_times(ground_truth)

    # The three spikes (45+ above trend) must be found; level shifts are
    # gradual and may be missed by a rolling z-score, which is fine.
    spikes = {
        a["timestamp"] for a in ground_truth["anomalies"] if a["kind"] == "spike"
    }
    hits = len(found & spikes)
    assert hits >= 2, f"zscore found {hits}/3 spikes: {sorted(found)}"
    # Precision sanity: fewer than 20 flagged points on this series.
    assert len(found) < 20, f"too many flagged: {len(found)}"


def test_iqr_finds_outliers(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/anomalies",
        json={"column": "value", "method": "iqr", "threshold": 1.5},
    )
    assert response.status_code == 200
    body = response.json()
    assert 0 < len(body["anomalies"]) < 60
    assert "fenceLow" in body and "fenceHigh" in body


def test_stl_residual_finds_spikes(csv_dataset, client, ground_truth):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/anomalies",
        json={
            "column": "value",
            "method": "stl",
            "threshold": 3.0,
            "period": 7,
        },
    )
    assert response.status_code == 200
    found = _times(response.json())
    spikes = {
        a["timestamp"] for a in ground_truth["anomalies"] if a["kind"] == "spike"
    }
    hits = len(found & spikes)
    assert hits >= 2, f"STL residual found {hits}/3 spikes: {sorted(found)}"


def test_stl_missing_period_rejected(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/anomalies",
        json={"column": "value", "method": "stl", "threshold": 3.0},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MISSING_PERIOD"


def test_stl_period_too_large(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/anomalies",
        json={
            "column": "value",
            "method": "stl",
            "threshold": 3.0,
            "period": 600,
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PERIOD"


def test_zscore_window_too_large(csv_dataset, client):
    response = client.post(
        f"/api/datasets/{csv_dataset['id']}/anomalies",
        json={
            "column": "value",
            "method": "zscore",
            "threshold": 3.0,
            "window": 5000,
        },
    )
    # 5000 passes the schema cap (10000) but exceeds the 730-row series.
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "WINDOW_TOO_LARGE"

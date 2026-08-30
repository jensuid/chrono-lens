"""Shared fixtures: a temp data dir and uploaded copies of the samples."""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SAMPLES = Path(__file__).resolve().parent.parent.parent / "sample_data"


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    """Isolate the dataset store per test."""
    monkeypatch.setenv("CHRONOLENS_DATA_DIR", str(tmp_path / "data"))
    yield tmp_path / "data"


@pytest.fixture()
def client(data_dir):
    """TestClient with an isolated store."""
    from app.main import app

    with TestClient(app) as c:
        yield c


def upload(client, name: str) -> dict:
    """Upload one sample file; assert success and return the meta."""
    path = SAMPLES / name
    with open(path, "rb") as f:
        response = client.post(
            "/api/datasets",
            files={"file": (name, f)},
        )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture()
def csv_dataset(client):
    return upload(client, "daily_metrics.csv")


@pytest.fixture()
def json_dataset(client):
    return upload(client, "sensor_feed.json")


@pytest.fixture()
def xlsx_dataset(client):
    return upload(client, "sales.xlsx")


@pytest.fixture(scope="session")
def ground_truth():
    import json

    return json.loads((SAMPLES / "ground_truth.json").read_text())

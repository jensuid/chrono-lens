"""Parsing and dataset CRUD tests."""

import io
import json

import pytest

from app.parsing import excel_sheets

from .conftest import SAMPLES, upload


def test_upload_csv_roundtrip(csv_dataset, ground_truth):
    assert csv_dataset["rows"] == ground_truth["nRows"]
    assert csv_dataset["datetimeColumn"] == "timestamp"
    assert "value" in csv_dataset["numericColumns"]
    assert csv_dataset["missing"]["value"] == ground_truth["missingCount"]


def test_upload_json(json_dataset, ground_truth):
    assert json_dataset["rows"] == ground_truth["nRows"]
    assert json_dataset["datetimeColumn"] == "ts"


def test_upload_xlsx_default_sheet_is_data(xlsx_dataset, ground_truth):
    # Default sheet is the first one, named "data" in sales.xlsx.
    assert xlsx_dataset["rows"] == ground_truth["nRows"]


def test_xlsx_sheet_listing():
    with open(SAMPLES / "sales.xlsx", "rb") as f:
        raw = f.read()
    assert excel_sheets(raw) == ["data", "readme"]


def test_upload_sheet_selection(client):
    with open(SAMPLES / "sales.xlsx", "rb") as f:
        response = client.post(
            "/api/datasets",
            files={"file": ("sales.xlsx", f)},
            data={"sheet": "readme"},
        )
    # The decoy sheet has no datetime/numeric pair: rejected with 422.
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_DATETIME_COLUMN"


def test_empty_file_rejected(client):
    response = client.post(
        "/api/datasets",
        files={"file": ("empty.csv", b"")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "EMPTY_FILE"


def test_unsupported_format_rejected(client):
    response = client.post(
        "/api/datasets",
        files={"file": ("notes.txt", b"hello")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNSUPPORTED_FORMAT"


def test_malformed_json_rejected(client):
    response = client.post(
        "/api/datasets",
        files={"file": ("bad.json", b"{not json")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "JSON_PARSE_ERROR"


def test_all_text_csv_rejected(client):
    response = client.post(
        "/api/datasets",
        files={"file": ("text.csv", b"word,other\nred,blue\n")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_DATETIME_COLUMN"


def test_duplicate_timestamps_aggregated(client):
    import pandas as pd

    buf = (
        "timestamp,value\n"
        "2023-01-01,10\n"
        "2023-01-01,20\n"
        "2023-01-02,5\n"
        "2023-01-03,8\n"
        "2023-01-04,9\n"
        "2023-01-05,7\n"
    )
    response = client.post(
        "/api/datasets",
        files={"file": ("dup.csv", buf.encode())},
    )
    assert response.status_code == 200
    meta = response.json()
    assert meta["rows"] == 5
    assert any("duplicate" in w for w in meta["warnings"])


def test_preview_returns_rows(csv_dataset, client):
    response = client.get(f"/api/datasets/{csv_dataset['id']}/preview?limit=5")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 730
    assert len(body["rows"]) == 5
    assert body["rows"][0]["timestamp"] == 1672531200000  # 2023-01-01 UTC


def test_delete(client, csv_dataset):
    response = client.delete(f"/api/datasets/{csv_dataset['id']}")
    assert response.status_code == 200
    response = client.get(f"/api/datasets/{csv_dataset['id']}")
    assert response.status_code == 404


def test_unknown_dataset_404(client):
    response = client.get("/api/datasets/doesnotexist")
    assert response.status_code == 404

"""Dataset endpoints: upload, metadata, preview, delete."""

import pandas as pd
from fastapi import APIRouter, Form, UploadFile

from . import parsing
from .errors import bad_request
from .store import MAX_UPLOAD_BYTES, Dataset, create_dataset, list_datasets

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post("")
async def upload(
    file: UploadFile,
    sheet: str | None = Form(default=None),
):
    """Parse and store an uploaded CSV/JSON/XLS/XLSX file."""
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise bad_request(
            "FILE_TOO_LARGE",
            f"file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB cap",
        )
    frame, warnings = parsing.parse_upload(raw, file.filename or "upload", sheet)
    ds = create_dataset(frame, warnings, source_name=file.filename or "upload")
    return _meta(ds)


@router.get("")
async def index():
    """Every stored dataset."""
    return list_datasets()


@router.get("/{dataset_id}")
async def meta(dataset_id: str):
    """Metadata: columns, dtypes, missing counts, time range."""
    return _meta(Dataset.load(dataset_id))


@router.get("/{dataset_id}/preview")
async def preview(dataset_id: str, limit: int = 200):
    """The first `limit` rows for the import preview table."""
    ds = Dataset.load(dataset_id)
    frame = ds.frame.head(limit)
    time = ds.time_range()
    return {
        "columns": [str(c) for c in frame.columns],
        "rows": _rows(frame),
        "total": int(len(ds.frame)),
    }


@router.delete("/{dataset_id}")
async def delete(dataset_id: str):
    """Delete a stored dataset."""
    ds = Dataset.load(dataset_id)
    ds.delete()
    return {"deleted": dataset_id}


def _meta(ds: Dataset) -> dict:
    """The metadata surface shared by upload and get."""
    frame = ds.frame
    time = ds.time_range()
    return {
        "id": ds.id,
        "name": ds.source_name,
        "rows": int(len(frame)),
        "columns": ds.column_labels(),
        "numericColumns": [
            str(c)
            for c in frame.columns
            if pd.api.types.is_numeric_dtype(frame[c])
        ],
        "datetimeColumn": time["column"],
        "missing": ds.missing_counts(),
        "warnings": ds.warnings,
        "timeRange": time,
    }


def _rows(frame: pd.DataFrame) -> list[dict]:
    """Records with epoch-ms timestamps and null for missing values."""
    out = []
    for record in frame.to_dict(orient="records"):
        clean = {}
        for key, value in record.items():
            if isinstance(value, pd.Timestamp):
                clean[str(key)] = (
                    None if pd.isna(value) else int(value.value // 1_000_000)
                )
            elif value is None or value != value:  # None or NaN
                clean[str(key)] = None
            elif hasattr(value, "item"):
                clean[str(key)] = value.item()
            else:
                clean[str(key)] = value
        out.append(clean)
    return out

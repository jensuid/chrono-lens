"""File parsing: CSV / JSON / XLS / XLSX into a normalized DataFrame.

The parser's contract:

- exactly one datetime column (auto-detected, user-overridable at the API
  layer) and at least one numeric column, or the file is rejected with a
  422 naming the problem;
- rows sorted by timestamp ascending; duplicate timestamps are aggregated
  (mean) and reported as a warning rather than an error;
- timestamps are stored UTC-naive; every later endpoint treats them as
  naive.

Sniffing rules for datetime candidates (first match wins, in column
order): a column whose pandas parse yields >= 90% valid datetimes, or a
column already typed datetime. Numeric candidates: float64/int64 dtypes
after coercion, or a column whose to_numeric conversion succeeds on >=
90% of values (missing values ignored in the ratio).
"""

import io
import json

import pandas as pd

from .errors import ApiError

DATE_PARSE_RATE = 0.9
NUMERIC_PARSE_RATE = 0.9


def reject_upload(code: str, message: str, detail=None) -> ApiError:
    """A 422 for an unusable upload."""
    return ApiError(422, code, message, detail)


def _detect_datetime(frame: pd.DataFrame) -> object | None:
    """Find the best datetime candidate column, or None."""
    for col in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[col]):
            return col
    for col in frame.columns:
        if frame[col].dtype == object:
            parsed = pd.to_datetime(frame[col], errors="coerce", format="mixed")
            if parsed.notna().mean() >= DATE_PARSE_RATE:
                return col
    return None


def _numeric_columns(frame: pd.DataFrame) -> list[object]:
    """Columns usable as analysis values."""
    out = []
    for col in frame.columns:
        if pd.api.types.is_numeric_dtype(frame[col]):
            out.append(col)
    if out:
        return out
    # No dtype-typed numeric columns: try coercion (files where numbers
    # arrived as strings).
    for col in frame.columns:
        if frame[col].dtype == object:
            coerced = pd.to_numeric(frame[col], errors="coerce")
            if coerced.notna().mean() >= NUMERIC_PARSE_RATE:
                frame[col] = coerced
                out.append(col)
    return out


def _normalize(
    frame: pd.DataFrame, source: str
) -> tuple[pd.DataFrame, list[str]]:
    """Attach the datetime index, sort, aggregate duplicates, collect warnings."""
    warnings: list[str] = []
    dt_col = _detect_datetime(frame)
    if dt_col is None:
        raise reject_upload(
            "NO_DATETIME_COLUMN",
            f"{source}: no datetime column detected",
            "the file needs a column parseable as timestamps",
        )
    if not pd.api.types.is_datetime64_any_dtype(frame[dt_col]):
        frame[dt_col] = pd.to_datetime(frame[dt_col], errors="coerce", format="mixed")
    frame = frame.dropna(subset=[dt_col])

    numeric = _numeric_columns(frame)
    if not numeric:
        raise reject_upload(
            "NO_NUMERIC_COLUMN",
            f"{source}: no numeric column detected",
            "the file needs at least one numeric value column",
        )

    before = len(frame)
    frame = frame.sort_values(dt_col)
    dup = int(frame.duplicated(subset=[dt_col]).sum())
    if dup:
        frame = frame.groupby(dt_col, as_index=False).mean(numeric_only=True)
        warnings.append(
            f"{dup} duplicate timestamps aggregated by mean ({before} -> {len(frame)} rows)"
        )
    frame = frame.reset_index(drop=True)
    return frame, warnings


def _parse_csv(raw: bytes) -> pd.DataFrame:
    """Parse CSV bytes; empty frames raise a 422."""
    try:
        frame = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001 - any parser failure is a 422
        raise reject_upload("CSV_PARSE_ERROR", "could not parse CSV", str(exc)) from exc
    if frame.empty:
        raise reject_upload("EMPTY_FILE", "CSV contains no data rows")
    return frame


def _parse_json(raw: bytes) -> pd.DataFrame:
    """Parse a JSON array of records; nested objects are flattened."""
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise reject_upload("JSON_PARSE_ERROR", "invalid JSON", str(exc)) from exc
    if not isinstance(data, list):
        raise reject_upload(
            "JSON_NOT_RECORDS", "JSON root must be an array of records"
        )
    if not data:
        raise reject_upload("EMPTY_FILE", "JSON array is empty")
    return pd.json_normalize(data)


def _parse_excel(raw: bytes) -> pd.DataFrame:
    """Parse XLSX/XLS bytes (first sheet)."""
    try:
        frame = pd.read_excel(io.BytesIO(raw))
    except Exception as exc:  # noqa: BLE001
        raise reject_upload(
            "EXCEL_PARSE_ERROR", "could not parse Excel file", str(exc)
        ) from exc
    if frame.empty:
        raise reject_upload("EMPTY_FILE", "Excel sheet contains no data rows")
    return frame


def excel_sheets(raw: bytes) -> list[str]:
    """Sheet names of an Excel workbook (for the import UI)."""
    try:
        if raw[:2] == b"PK":
            import openpyxl

            return openpyxl.load_workbook(io.BytesIO(raw), read_only=True).sheetnames
        import xlrd

        return xlrd.open_workbook(file_contents=raw).sheet_names()
    except Exception as exc:  # noqa: BLE001
        raise reject_upload(
            "EXCEL_PARSE_ERROR", "could not read Excel sheets", str(exc)
        ) from exc


def parse_upload(
    raw: bytes, filename: str, sheet: str | None = None
) -> tuple[pd.DataFrame, list[str]]:
    """Sniff format by extension + magic bytes; parse; normalize."""
    if len(raw) == 0:
        raise reject_upload("EMPTY_FILE", f"{filename} is empty")
    lower = filename.lower()
    if lower.endswith(".csv"):
        frame = _parse_csv(raw)
    elif lower.endswith(".json"):
        frame = _parse_json(raw)
    elif lower.endswith((".xlsx", ".xls")):
        try:
            frame = pd.read_excel(io.BytesIO(raw), sheet_name=sheet or 0)
        except Exception as exc:  # noqa: BLE001
            raise reject_upload(
                "EXCEL_PARSE_ERROR", "could not parse Excel file", str(exc)
            ) from exc
        if frame.empty:
            raise reject_upload("EMPTY_FILE", "Excel sheet contains no data rows")
    else:
        raise reject_upload(
            "UNSUPPORTED_FORMAT",
            f"unsupported file type: {filename}",
            "supported: .csv, .json, .xlsx, .xls",
        )
    return _normalize(frame, filename)

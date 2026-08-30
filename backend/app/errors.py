"""Uniform API error envelopes and helpers.

Every failing endpoint answers a JSON body of the shape::

    {"error": {"code": "...", "message": "...", "detail": ...}}

`code` is a stable machine-readable identifier the frontend can branch on;
`message` is human-readable; `detail` carries structured context (e.g. the
offending column name) and is optional.
"""

from fastapi import HTTPException

import pandas as pd


class ApiError(HTTPException):
    """An error carrying a stable code alongside the HTTP status."""

    def __init__(self, status: int, code: str, message: str, detail=None):
        super().__init__(status_code=status, detail=message)
        self.code = code
        self.message = message
        self.detail = detail


def bad_request(code: str, message: str, detail=None) -> ApiError:
    """A 400 with a stable code."""
    return ApiError(400, code, message, detail)


def not_found(message: str) -> ApiError:
    """A 404 for a missing dataset or resource."""
    return ApiError(404, "NOT_FOUND", message)


def serialization_fallback(value):
    """Map pandas/numpy values into JSON-safe primitives.

    NaN and NaT become None (the API contract serializes missing values as
    null); numpy scalars become plain Python scalars; Timestamps become
    epoch milliseconds.
    """
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else int(value.value // 1_000_000)
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value

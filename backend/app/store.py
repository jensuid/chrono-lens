"""Dataset registry and parquet persistence for uploaded files.

Uploaded files are parsed once, normalized (sorted, UTC-naive timestamps),
and persisted as parquet under a per-dataset directory. Every analysis
endpoint is a pure read over the stored frame; nothing mutates it.
"""

import os
import sys
import uuid
from pathlib import Path

import pandas as pd

from .errors import not_found

# Upload cap: the parser holds the whole frame in memory, so bound it.
MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _default_data_dir() -> Path:
    """Per-user writable storage.

    Never a relative path: Finder-launched apps run with cwd=/ (a
    read-only volume on modern macOS), and a relative 'appdata' would
    try to create /appdata and crash every store-touching endpoint.
    """
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ChronoLens"
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "ChronoLens"
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(base) / "chronolens"


def _data_dir() -> Path:
    """The dataset storage directory (overridable for tests via env)."""
    root = Path(os.environ.get("CHRONOLENS_DATA_DIR") or _default_data_dir())
    root.mkdir(parents=True, exist_ok=True)
    return root


def _source_name_path(data_dir: Path, dataset_id: str) -> Path:
    """Sidecar holding the original upload filename."""
    return data_dir / f"{dataset_id}.source.json"


def _read_source_name(data_dir: Path, dataset_id: str) -> str:
    import json

    path = _source_name_path(data_dir, dataset_id)
    if path.exists():
        try:
            return str(json.loads(path.read_text()).get("name", ""))
        except (json.JSONDecodeError, OSError):
            return ""
    return ""


class Dataset:
    """One stored dataset: its frame plus cached metadata."""

    def __init__(
        self,
        dataset_id: str,
        frame: pd.DataFrame,
        warnings: list[str],
        source_name: str = "",
    ):
        self.id = dataset_id
        self.warnings = warnings
        self.source_name = source_name
        self._frame = frame

    # -- loading -----------------------------------------------------------

    @classmethod
    def load(cls, dataset_id: str) -> "Dataset":
        """Load a stored dataset by id or raise 404."""
        path = _data_dir() / f"{dataset_id}.parquet"
        if not path.exists():
            raise not_found(f"dataset {dataset_id} does not exist")
        frame = pd.read_parquet(path)
        warnings_path = _data_dir() / f"{dataset_id}.warnings.json"
        import json

        warnings = []
        if warnings_path.exists():
            warnings = json.loads(warnings_path.read_text())
        source_name = _read_source_name(_data_dir(), dataset_id)
        return cls(dataset_id, frame, warnings, source_name)

    def save(self, source_name: str | None = None) -> None:
        """Persist the frame, warnings, and source filename."""
        import json

        data_dir = _data_dir()
        path = data_dir / f"{self.id}.parquet"
        self._frame.to_parquet(path)
        (data_dir / f"{self.id}.warnings.json").write_text(
            json.dumps(self.warnings)
        )
        if source_name is not None:
            self.source_name = source_name
        _source_name_path(data_dir, self.id).write_text(
            json.dumps({"name": self.source_name})
        )

    def delete(self) -> None:
        """Remove this dataset's stored artifacts."""
        for path in _data_dir().glob(f"{self.id}.*"):
            path.unlink()

    # -- accessors ---------------------------------------------------------

    @property
    def frame(self) -> pd.DataFrame:
        """The stored, immutable-by-convention DataFrame."""
        return self._frame

    def column_labels(self) -> dict[str, str]:
        """Column name -> pandas dtype label for metadata surfaces."""
        return {str(c): str(t) for c, t in self._frame.dtypes.items()}

    def missing_counts(self) -> dict[str, int]:
        """Per-column missing-value counts."""
        return {str(c): int(self._frame[c].isna().sum()) for c in self._frame.columns}

    def time_range(self) -> dict:
        """First/last timestamp of the datetime column."""
        col = _datetime_column(self._frame)
        series = self._frame[col]
        return {
            "column": str(col),
            "first": None if series.empty else series.iloc[0].value // 1_000_000,
            "last": None if series.empty else series.iloc[-1].value // 1_000_000,
            "rows": int(len(self._frame)),
        }


def _datetime_column(frame: pd.DataFrame) -> object:
    """The first datetime-typed column; the parser guarantees one exists."""
    for col in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[col]):
            return col
    raise not_found("dataset has no datetime column")


def create_dataset(
    frame: pd.DataFrame, warnings: list[str], source_name: str = ""
) -> Dataset:
    """Persist a new dataset under a fresh id."""
    dataset_id = uuid.uuid4().hex[:12]
    ds = Dataset(dataset_id, frame, warnings, source_name)
    ds.save(source_name=source_name)
    return ds


def list_datasets() -> list[dict]:
    """Minimal metadata for every stored dataset, newest first.

    Reads only the small sidecars plus parquet *metadata* (row count)
    instead of loading every full frame — listing must stay fast as
    datasets accumulate. Sorted by file modification time so recently
    imported datasets appear first.
    """
    import json

    import pyarrow.parquet as pq

    data_dir = _data_dir()
    out = []
    for path in data_dir.glob("*.parquet"):
        dataset_id = path.stem
        warnings: list = []
        warnings_path = data_dir / f"{dataset_id}.warnings.json"
        if warnings_path.exists():
            warnings = json.loads(warnings_path.read_text())
        meta = pq.read_metadata(path)
        out.append(
            {
                "id": dataset_id,
                "name": _read_source_name(data_dir, dataset_id),
                "rows": meta.num_rows,
                "warnings": warnings,
                "timeRange": _parquet_time_range(path),
                "mtime": path.stat().st_mtime,
            }
        )
    out.sort(key=lambda d: d["mtime"], reverse=True)
    for entry in out:
        entry.pop("mtime", None)
    return out


def _parquet_time_range(path: Path) -> dict:
    """First/last timestamp from parquet statistics, without loading data."""
    import pyarrow.parquet as pq

    meta = pq.read_metadata(path)
    names = meta.schema.names
    dt_col = next((n for n in names if "timestamp" in str(n).lower()), names[0])
    for i in range(meta.num_row_groups):
        stats = meta.row_group(i).column(names.index(dt_col)).statistics
        if stats is not None and stats.has_min_max:
            return {
                "column": str(dt_col),
                "first": int(pd.Timestamp(stats.min).value // 1_000_000),
                "last": int(pd.Timestamp(stats.max).value // 1_000_000),
                "rows": int(meta.num_rows),
            }
    return {"column": str(dt_col), "first": None, "last": None, "rows": int(meta.num_rows)}

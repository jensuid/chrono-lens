"""Store behavior: writable, absolute data dir regardless of cwd.

The shipped bug: launched from Finder, the app ran with cwd=/ (read-only
system volume); the store's *relative* default 'appdata' resolved to
/appdata, mkdir failed, and every store-touching endpoint 500'd — masked
by CORS into WKWebView's 'Load failed'.
"""

import os
from pathlib import Path

import pytest

from app import store


def test_default_data_dir_is_absolute() -> None:
    """The default must never be a bare relative path."""
    path = store._default_data_dir()
    assert path.is_absolute(), f"default data dir is relative: {path}"


def test_default_data_dir_is_writable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default location must be creatable and writable for this user."""
    monkeypatch.setenv("HOME", str(tmp_path))
    path = store._default_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".write-probe"
    probe.write_text("ok")
    assert probe.read_text() == "ok"


def test_env_override_still_works(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """CHRONOLENS_DATA_DIR keeps overriding the default (tests rely on it)."""
    monkeypatch.setenv("CHRONOLENS_DATA_DIR", str(tmp_path / "custom"))
    assert store._data_dir() == tmp_path / "custom"


def test_store_roundtrip_from_readonly_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Upload + list must work even when the process cwd is read-only.

    Reproduces the Finder launch condition: with cwd on a read-only
    volume, the old relative default broke; the absolute default must
    not care about cwd at all.
    """
    monkeypatch.delenv("CHRONOLENS_DATA_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / "readonly").mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(tmp_path / "readonly")  # cwd irrelevant to the store now

    import pandas as pd

    frame = pd.DataFrame(
        {"timestamp": pd.to_datetime(["2024-01-01", "2024-01-02"]), "value": [1.0, 2.0]}
    )
    ds = store.create_dataset(frame, warnings=[])
    loaded = store.Dataset.load(ds.id)
    assert len(loaded.frame) == 2
    assert [d["id"] for d in store.list_datasets()] == [ds.id]

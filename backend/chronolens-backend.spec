# PyInstaller spec for the ChronoLens backend sidecar.
# Freeze mode: one-file binary named chronolens-backend; Tauri stages it
# as binaries/chronolens-backend-x86_64-apple-darwin.

import sys
from pathlib import Path

BACKEND_ROOT = Path(SPECPATH).resolve()
APP_DIR = BACKEND_ROOT / "app"

a = Analysis(
    [str(APP_DIR / "sidecar_entry.py")],
    pathex=[str(APP_DIR.parent), str(APP_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # uvicorn internals discovered only at runtime
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # statsmodels lazy-loaded submodules
        "statsmodels.tsa.seasonal",
        "statsmodels.tsa.stattools",
        "statsmodels.tsa.holtwinters",
        "statsmodels.tsa.statespace.sarimax",
        # pandas/pyarrow extras pulled dynamically
        "pyarrow.parquet",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="chronolens-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,  # sidecar: stderr must be visible for debugging
    icon=None,
)

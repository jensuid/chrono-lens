# ChronoLens — Time Series Analysis Desktop App

ChronoLens is a macOS desktop application for exploring, decomposing,
forecasting, and anomaly-screening time series data. It imports CSV, JSON
(array of records), and Excel (`.xlsx` / `.xls`) files, analyzes them with
pandas / statsmodels / scipy, and renders interactive charts in a native
window.

## Stack

- **Shell:** Tauri 2 (Rust, system WebKit — small footprint, no bundled Chromium)
- **UI:** Vue 3 + Vite + ECharts
- **Analysis:** Python 3.11 — FastAPI sidecar embedding pandas, numpy,
  scipy, statsmodels (STL, SARIMA, Holt-Winters, ADF/KPSS, ACF/PACF),
  openpyxl/xlrd for Excel formats
- **Packaging:** the Python backend is frozen with PyInstaller into a
  single-file binary and spawned by the Tauri shell as an external sidecar
  on a free localhost port.

## Project layout

```
sample_data/     synthetic demo datasets (CSV / JSON / XLSX) + ground truth
backend/         FastAPI analysis service, tests, PyInstaller spec
  app/           parsing, dataset store, analysis endpoints
  tests/         pytest suite (httpx TestClient)
src/             Vue 3 frontend (views, components, api)
src-tauri/       Tauri shell (sidecar spawn, port picking, capabilities)
scripts/         build_app.sh — full build pipeline
```

## Run from source (development)

Requirements: Python 3.11, Node 18+.

```sh
# 1. Python backend (once)
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Start the analysis service on the dev port
.venv/bin/uvicorn app.main:app --port 8756 --reload

# 3. In another terminal: frontend dev server (proxies /api -> 8756)
cd src
npm install
npm run dev
```

Open the printed Vite URL (http://localhost:5173) in a browser, or run
`npm run tauri dev` for the desktop window in development mode.

## Build the .app

```sh
scripts/build_app.sh
```

The script:

1. creates `backend/.venv` and installs requirements (skipped when it exists),
2. freezes the backend with PyInstaller into a single-file binary,
3. stages it under `src-tauri/binaries/` with Tauri's sidecar naming
   (`chronolens-backend-x86_64-apple-darwin`),
4. runs `npm install` for the frontend,
5. runs the Tauri release build with `CARGO_HOME` pointed at a
   workspace-local directory (the build machine's `~/.cargo` is not
   writable by the build sandbox),
6. leaves the result at
   `src-tauri/target/release/bundle/macos/ChronoLens.app`.

The build is fully resumable: pip, npm, and cargo caches make every long
step incremental, so re-running the script after an interruption picks up
where it left off.

## Using the app

1. Launch `ChronoLens.app`. On first run macOS shows an unidentified
   developer dialog because the app is unsigned — right-click the app and
   choose **Open** (see Known Limitations).
2. **Import:** drop a CSV / JSON / XLS / XLSX file (or click to browse).
   ChronoLens detects the datetime and numeric columns and previews the
   parsed rows; pick the value column and, for Excel, the sheet.
3. **Explore:** full-series chart with zoom (drag inside the chart),
   descriptive stats, missing-value report, resampling, and rolling
   statistics.
4. **Decompose:** STL or classical decomposition into
   observed/trend/seasonal/residual components; ADF and KPSS stationarity
   tests with interpretation; ACF/PACF with confidence bands.
5. **Forecast:** SARIMA or Holt-Winters models with a train/test
   backtest split, fitted values, forecast with confidence interval, and
   MAE / RMSE / MAPE error metrics.
6. **Anomalies:** rolling z-score, IQR, or STL-residual anomaly detection
   with severity scores and a highlighted chart.

Sample files for a first tour live in `sample_data/` — the same series in
all three formats, with injected anomalies whose locations are listed in
`ground_truth.json`.

## Development notes

- `backend/generate_sample.py` regenerates `sample_data/` deterministically
  (fixed seed).
- Backend API errors are uniform JSON envelopes:
  `{"error": {"code": "...", "message": "...", "detail": ...}}`.
- All timestamps cross the API as epoch milliseconds; NaN values are
  serialized as `null`.
- Backend tests: `cd backend && .venv/bin/python -m pytest`.

## Data Storage

Imported datasets persist as parquet under a per-user directory:

- macOS: `~/Library/Application Support/ChronoLens`
- Linux: `~/.local/share/chronolens`
- Windows: `%APPDATA%/ChronoLens`

The location is resolved absolutely at runtime (never relative to the
process working directory) and can be overridden for development or
testing with the `CHRONOLENS_DATA_DIR` environment variable.

## Known Limitations and Deferred Work

- **First launch is slow (~1 minute):** the sidecar is a PyInstaller
  one-file binary that unpacks its embedded Python stack to a temporary
  directory on every start; the window opens but analyses wait until the
  backend reports healthy.
- **Unsigned app:** no code signing / notarization — Gatekeeper requires
  right-click → Open (or `xattr -d com.apple.quarantine` after copying).
  Only an Intel (x86_64) build is produced.
- **App size:** the embedded Python stack makes the .app ~150–250 MB.
- **No model persistence:** analysis results are not exported (chart PNG
  export via the ECharts toolbar only).
- **No SARIMA order auto-selection:** sensible defaults plus manual order
  controls.
- **JSON input:** array-of-records only (nested objects flattened); no
  NDJSON.
- **No streaming series:** static files only; no live-updating feeds.
- **Single-series analyses:** each view analyzes one value column per
  dataset.

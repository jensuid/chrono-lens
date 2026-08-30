#!/bin/bash
# ChronoLens full build pipeline. Resumable: every long step caches
# (pip venv, npm, cargo target dir), so re-running after an interruption
# picks up where it left off.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/src"
TAURI_DIR="$ROOT/src-tauri"
CARGO_HOME="${CHRONOLENS_CARGO_HOME:-$ROOT/.cargo-home}"
SIDECAR_TRIPLE="chronolens-backend-x86_64-apple-darwin"

cd "$ROOT"
echo "== ChronoLens build =="
echo "root: $ROOT"
echo "cargo home: $CARGO_HOME"

# ---------------------------------------------------------------------------
# Stage 1: Python venv
# ---------------------------------------------------------------------------
if [ ! -x "$BACKEND/.venv/bin/python" ]; then
  echo "== stage 1: creating Python venv =="
  python3 -m venv "$BACKEND/.venv"
  "$BACKEND/.venv/bin/pip" install --quiet --upgrade pip
fi
if [ ! -x "$BACKEND/.venv/bin/uvicorn" ] || [ "$BACKEND/requirements.txt" -nt "$BACKEND/.venv/.installed" ]; then
  echo "== stage 1: installing requirements =="
  "$BACKEND/.venv/bin/pip" install --quiet -r "$BACKEND/requirements.txt"
  touch "$BACKEND/.venv/.installed"
fi

# ---------------------------------------------------------------------------
# Stage 2: backend tests (fast gate before freezing)
# ---------------------------------------------------------------------------
echo "== stage 2: backend tests =="
"$BACKEND/.venv/bin/python" -m pytest "$BACKEND/tests" -q --tb=line

# ---------------------------------------------------------------------------
# Stage 3: PyInstaller sidecar binary (skipped when spec+sources unchanged)
# ---------------------------------------------------------------------------
FREEZE_HASH_FILE="$BACKEND/.freeze-hash"
FREEZE_HASH=$( (cat "$BACKEND/chronolens-backend.spec"; cat "$BACKEND"/app/*.py) | shasum | cut -d' ' -f1)
if [ -f "$FREEZE_HASH_FILE" ] && [ "$(cat "$FREEZE_HASH_FILE")" = "$FREEZE_HASH" ] && [ -f "$TAURI_DIR/binaries/$SIDECAR_TRIPLE" ]; then
  echo "== stage 3: freeze unchanged, reusing sidecar =="
else
  echo "== stage 3: freezing backend =="
  (
    cd "$BACKEND"
    .venv/bin/pyinstaller --noconfirm --clean chronolens-backend.spec
  )
  echo "$FREEZE_HASH" > "$FREEZE_HASH_FILE"
fi
mkdir -p "$TAURI_DIR/binaries"
cp "$BACKEND/dist/chronolens-backend" "$TAURI_DIR/binaries/$SIDECAR_TRIPLE"
echo "sidecar staged: $TAURI_DIR/binaries/$SIDECAR_TRIPLE"

# ---------------------------------------------------------------------------
# Stage 4: frontend dependencies
# ---------------------------------------------------------------------------
if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "== stage 4: npm install =="
  (cd "$FRONTEND" && npm install --no-audit --no-fund)
else
  echo "== stage 4: node_modules present =="
fi

# ---------------------------------------------------------------------------
# Stage 5: Tauri release build (long; resumable via cargo target dir)
# ---------------------------------------------------------------------------
# The CLI must run from the project root: it discovers src-tauri/ by
# searching subfolders for tauri.conf.json.
echo "== stage 5: tauri build =="
(
  cd "$ROOT"
  PATH="$FRONTEND/node_modules/.bin:$PATH" CARGO_HOME="$CARGO_HOME" tauri build
)

APP="$TAURI_DIR/target/release/bundle/macos/ChronoLens.app"
echo "== build complete: $APP =="
test -d "$APP"

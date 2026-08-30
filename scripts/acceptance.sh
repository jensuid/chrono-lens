#!/bin/bash
# Acceptance test for the packaged ChronoLens.app.
# Launches the app, waits for the sidecar, exercises the API end to end
# (all three sample formats, decompose, forecast, anomalies), then quits
# and verifies no orphan sidecar remains.
#
# Usage: scripts/acceptance.sh
# Exits 0 on success.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
APP="src-tauri/target/release/bundle/macos/ChronoLens.app/Contents/MacOS/chrono-lens"
TRACE=/tmp/chronolens-acceptance.log

[ -x "$APP" ] || { echo "FAIL: $APP missing — run scripts/build_app.sh first"; exit 1; }

pkill -f chronolens-backend 2>/dev/null || true
sleep 1

"$APP" > "$TRACE" 2>&1 &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true; pkill -f chronolens-backend 2>/dev/null || true' EXIT

# --- sidecar port from the shell's own stdout -----------------------------
PORT=""
for _ in $(seq 1 30); do
  PORT=$(grep -o "port [0-9]*" "$TRACE" 2>/dev/null | grep -o "[0-9]*$" | head -1 || true)
  [ -n "$PORT" ] && break
  sleep 2
done
[ -n "$PORT" ] || { echo "FAIL: sidecar port not found"; exit 1; }
echo "sidecar port: $PORT"

# --- health ----------------------------------------------------------------
for _ in $(seq 1 45); do
  R=$(curl -s --max-time 3 "http://127.0.0.1:$PORT/api/health" 2>/dev/null || true)
  [ -n "$R" ] && { echo "health: $R"; break; }
  sleep 2
done
[ -n "${R:-}" ] || { echo "FAIL: backend never became healthy"; exit 1; }

# --- CORS: the webview origin must be allowed (regression: "Load failed") ---
ALLOWED=$(curl -s -o /dev/null -w "%{header_json}" --max-time 5 \
  -H "Origin: tauri://localhost" \
  "http://127.0.0.1:$PORT/api/health" \
  | python3 -c "import json,sys; print(json.load(sys.stdin).get('access-control-allow-origin', [''])[0])")
[ "$ALLOWED" = "tauri://localhost" ] || { echo "FAIL: webview origin blocked by CORS (got '$ALLOWED')"; exit 1; }
echo "CORS ok: webview origin tauri://localhost allowed"

# --- uploads (all three formats) --------------------------------------------
for f in daily_metrics.csv sensor_feed.json sales.xlsx; do
  U=$(curl -s --max-time 90 -F "file=@sample_data/$f" "http://127.0.0.1:$PORT/api/datasets")
  ROWS=$(echo "$U" | python3 -c "import json,sys; print(json.load(sys.stdin)['rows'])" 2>/dev/null || echo "")
  [ "$ROWS" = "730" ] || { echo "FAIL: $f parsed to '${ROWS:-error}' rows"; exit 1; }
  echo "upload ok: $f (730 rows)"
done

DSID=$(curl -s -F "file=@sample_data/daily_metrics.csv" "http://127.0.0.1:$PORT/api/datasets" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# --- STL decomposition ------------------------------------------------------
AMP=$(curl -s --max-time 120 -X POST -H "Content-Type: application/json" \
  -d '{"column":"value","period":7,"method":"stl"}' \
  "http://127.0.0.1:$PORT/api/datasets/$DSID/decompose" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); s=[p['v'] for p in d['seasonal'] if p['v'] is not None]; print(round((max(s)-min(s))/2,1))")
echo "STL seasonal amplitude: $AMP (weekly signal present: $([ $(echo "$AMP > 4" | bc) = 1 ] && echo yes || echo NO))"

# --- SARIMA forecast ----------------------------------------------------------
METRICS=$(curl -s --max-time 180 -X POST -H "Content-Type: application/json" \
  -d '{"column":"value","horizon":30,"trainRatio":0.8,"order":[1,1,1],"seasonalOrder":[1,0,1,7]}' \
  "http://127.0.0.1:$PORT/api/datasets/$DSID/forecast/sarima" \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['metrics']['mae'], len(d['forecast']['points']))")
echo "SARIMA (mae, horizon points): $METRICS"

# --- anomalies ------------------------------------------------------------------
ANOM=$(curl -s --max-time 120 -X POST -H "Content-Type: application/json" \
  -d '{"column":"value","method":"zscore","threshold":4.0,"window":14}' \
  "http://127.0.0.1:$PORT/api/datasets/$DSID/anomalies" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)['anomalies']))")
echo "anomalies flagged: $ANOM"
[ "$ANOM" -ge 3 ] || { echo "FAIL: expected >=3 anomalies (spikes)"; exit 1; }

# --- graceful quit reaps the sidecar ---------------------------------------------
osascript -e 'tell application "ChronoLens" to quit' 2>/dev/null || true
sleep 5
# grep exits 1 on zero matches, which set -e would treat as failure;
# `|| true` keeps the count (0) flowing.
LEFT=$(ps aux | grep "[c]hronolens-backend" | wc -l | tr -d ' ' || true)
LEFT=${LEFT:-0}
if [ "$LEFT" = "0" ]; then
  echo "PASS: no orphan sidecar after quit"
else
  echo "FAIL: $LEFT sidecar process(es) survived quit"
  ps aux | grep "[c]hronolens-backend" | head -3
  exit 1
fi

echo ""
echo "ALL ACCEPTANCE CHECKS PASSED"

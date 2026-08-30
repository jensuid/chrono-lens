"""Generate the synthetic sample datasets deterministically (seed 42).

Writes into ../sample_data (relative to this file):

- daily_metrics.csv  — ~730 daily rows: linear trend + weekly seasonality
                       (period 7) + yearly seasonality + noise + 3 spikes +
                       3 level shifts + ~2% missing values
- sensor_feed.json   — same series as a JSON array of records
- sales.xlsx         — same series, with a decoy second sheet
- ground_truth.json  — injected anomaly indices and true period

The generator is the acceptance fixture: tests assert that the anomaly
endpoints recall the injected spikes and that STL recovers the weekly
period.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

SEED = 42
N_DAYS = 730
START = datetime(2023, 1, 1, tzinfo=timezone.utc)
PERIOD = 7
MISSING_RATE = 0.02
OUT_DIR = Path(__file__).resolve().parent.parent / "sample_data"


def build_series() -> tuple[np.ndarray, list[dict]]:
    """The daily value array plus ground-truth anomaly records."""
    rng = np.random.default_rng(SEED)
    days = np.arange(N_DAYS)
    # Components: trend + weekly + yearly + noise
    trend = 100.0 + 0.05 * days
    weekly = 8.0 * np.sin(2 * np.pi * days / PERIOD)
    yearly = 15.0 * np.sin(2 * np.pi * days / 365.25)
    noise = rng.normal(0, 3.0, N_DAYS)
    values = trend + weekly + yearly + noise

    anomalies: list[dict] = []
    # 3 spikes: +12..18 sigma-ish jumps (sigma=3)
    for i, day in enumerate((120, 365, 610)):
        values[day] += 45 + 10 * i
        anomalies.append({"index": day, "kind": "spike", "magnitude": 45 + 10 * i})
    # 3 level shifts lasting 14 days
    for i, day in enumerate((200, 430, 650)):
        values[day : day + 14] -= 30 + 5 * i
        anomalies.append(
            {"index": day, "kind": "level_shift", "magnitude": -(30 + 5 * i), "length": 14}
        )
    return values, anomalies


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    values, anomalies = build_series()
    rng = np.random.default_rng(SEED + 1)

    timestamps = [START + timedelta(days=int(i)) for i in range(N_DAYS)]

    # ~2% missing values (never on injected anomaly days, so tests are fair)
    anomaly_days = {a["index"] for a in anomalies} | {
        i for a in anomalies if a["kind"] == "level_shift" for i in range(a["index"], a["index"] + a.get("length", 0))
    }
    missing_mask = np.zeros(N_DAYS, dtype=bool)
    while missing_mask.sum() < MISSING_RATE * N_DAYS:
        idx = int(rng.integers(0, N_DAYS))
        if idx not in anomaly_days:
            missing_mask[idx] = True

    import pandas as pd

    frame = pd.DataFrame(
        {
            "timestamp": [ts.strftime("%Y-%m-%d") for ts in timestamps],
            "value": [None if m else float(v) for v, m in zip(values, missing_mask, strict=True)],
        }
    )
    frame.to_csv(OUT_DIR / "daily_metrics.csv", index=False)

    # JSON variant: array of records with ISO timestamps.
    records = [
        {"ts": ts.isoformat(), "reading": None if m else round(float(v), 4)}
        for ts, v, m in zip(timestamps, values, missing_mask, strict=True)
    ]
    (OUT_DIR / "sensor_feed.json").write_text(json.dumps(records, indent=1))

    # XLSX variant with a decoy sheet.
    with pd.ExcelWriter(OUT_DIR / "sales.xlsx") as writer:
        frame.to_excel(writer, sheet_name="data", index=False)
        pd.DataFrame({"note": ["decoy sheet; pick 'data' in the import UI"]}).to_excel(
            writer, sheet_name="readme", index=False
        )

    ground_truth = {
        "seed": SEED,
        "period": PERIOD,
        "nRows": N_DAYS,
        "missingCount": int(missing_mask.sum()),
        "anomalies": [
            {
                **a,
                "timestamp": timestamps[a["index"]].strftime("%Y-%m-%d"),
            }
            for a in anomalies
        ],
    }
    (OUT_DIR / "ground_truth.json").write_text(json.dumps(ground_truth, indent=1))

    print(f"wrote {len(frame)} rows to {OUT_DIR}")
    print(f"anomalies: {[a['timestamp'] + ' (' + a['kind'] + ')' for a in ground_truth['anomalies']]}")


if __name__ == "__main__":
    main()

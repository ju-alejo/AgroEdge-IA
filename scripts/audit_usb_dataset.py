"""Summarize a read-only snapshot of the USB measurement database, including its WAL."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from statistics import mean, median

from scripts.tinyml_dataset import MAX_GAP, MIN_GAP, WINDOW, utc


def read_snapshot(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        counts = dict(db.execute("SELECT origin, count(*) FROM real_readings GROUP BY origin"))
        simulated = db.execute("SELECT count(*) FROM simulated_readings").fetchone()[0]
        raw = db.execute("SELECT payload, fingerprint IS NOT NULL FROM real_readings WHERE origin='USB' "
                         "ORDER BY station,session,seq").fetchall()
    return counts, simulated, [(json.loads(payload), bool(ingested)) for payload, ingested in raw]


def distribution(values):
    if not values:
        return None
    return {"min": min(values), "median": median(values), "mean": round(mean(values), 3), "max": max(values)}


def summarize_session(records):
    stamps = [utc(row["acquiredAt"]) for row, _ in records]
    first, last = records[0][0], records[-1][0]
    gaps, intervals, labels = 0, [], Counter()
    runs = {"physical": 0, "training": 0}
    training_windows = 0
    first_classified_window = None
    previous = None
    for (row, ingested), stamp in zip(records, stamps, strict=True):
        continuous = True
        if previous:
            sequence_gap = row["sequence"] - previous[0] - 1
            seconds = (stamp - previous[1]).total_seconds()
            gaps += max(0, sequence_gap)
            if sequence_gap == 0:
                intervals.append(seconds)
            continuous = sequence_gap == 0 and MIN_GAP.total_seconds() <= seconds <= MAX_GAP.total_seconds()
            if not continuous:
                runs = dict.fromkeys(runs, 0)
        quality = row["quality"]
        runs["physical"] = runs["physical"] + 1 if ingested and quality in ("VALID", "ANOMALY") else 0
        runs["training"] = runs["training"] + 1 if ingested and continuous and quality == "VALID" else 0
        if runs["training"] == WINDOW:
            training_windows += 1
            runs["training"] = 0
        result = row["classification"]
        if result:
            labels[f'{result["source"]}/{result["modelVersion"]}/{result["state"]}'] += 1
            if (runs["physical"] >= WINDOW and first_classified_window is None and result["source"] == "ESP32"
                    and result["state"] == "OK" and type(result.get("inferenceUs")) is int):
                first_classified_window = {"first_sequence": row["sequence"] - WINDOW + 1,
                                           "last_sequence": row["sequence"], "classification": result}
        previous = row["sequence"], stamp

    return {"station": first["stationId"], "session": first["sessionId"], "rows": len(records),
            "start": min(stamps).isoformat(), "end": max(stamps).isoformat(),
            "first_sequence": first["sequence"], "last_sequence": last["sequence"], "missing_sequences_inside": gaps,
            "quality": Counter(row["quality"] for row, _ in records),
            "ingested": sum(ingested for _, ingested in records),
            "time_sources": Counter(row["timeSource"] for row, _ in records),
            "consecutive_intervals_s": distribution(intervals), "intervals_over_8_s": sum(i > 8 for i in intervals),
            "intervals_under_4_s": sum(i < 4 for i in intervals),
            "intervals_non_increasing": sum(i <= 0 for i in intervals),
            "values": {key: distribution([row[key] for row, _ in records if row[key] is not None])
                       for key in ("temperature", "humidity", "pressure")},
            "training_windows_before_labeling": training_windows, "classification_counts": labels,
            "first_classified_window": first_classified_window}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/agroedge.sqlite"))
    args = parser.parse_args()
    counts, simulated, records = read_snapshot(args.db)
    snapshot_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    grouped = defaultdict(list)
    for row, ingested in records:
        grouped[row["stationId"], row["sessionId"]].append((row, ingested))
    sessions = sorted((summarize_session(group) for group in grouped.values()), key=lambda group: group["start"])
    issues = Counter(issue.split(" se apartó ", 1)[0] for row, _ in records if row["quality"] == "ANOMALY"
                     for issue in row["issues"])
    print(json.dumps({"snapshot_at": snapshot_at, "real_by_origin": counts, "simulated": simulated,
                      "usb_anomaly_variables": issues, "usb_sessions": sessions}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Create a versioned observational dataset from an AgroEdge SQLite backup."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import mean, median, stdev
from tempfile import TemporaryDirectory

from scripts.audit_usb_dataset import read_snapshot
from scripts.tinyml_dataset import MAX_GAP, MIN_GAP, utc


SENSORS = {"temperature": "temperature_c", "humidity": "relative_humidity_pct", "pressure": "station_pressure_hpa"}


def digest(path):
    result = sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            result.update(chunk)
    return result.hexdigest()


def summaries(readings):
    result = {}
    for sensor, column in SENSORS.items():
        values = [r[sensor] for r in readings if r[sensor] is not None]
        summary = {"n": len(values), "missing": len(readings) - len(values)}
        if values:
            summary |= {"min": min(values), "mean": round(mean(values), 4),
                        "median": round(median(values), 4), "max": max(values),
                        "sample_sd": round(stdev(values), 4) if len(values) > 1 else None}
        result[column] = summary
    return result


def context_at(stamp, move_start, move_end, settled):
    if stamp < move_start:
        return "greenhouse", "before_move"
    if stamp < move_end:
        return "uncertain_during_move", "transfer"
    if stamp < settled:
        return "outdoor", "settling"
    return "outdoor", "after_provisional_settling"


def derive(readings, campaign, move_start, move_end, settled):
    stamps = [utc(row["receivedAt"]) for row in readings]
    intervals = [(right - left).total_seconds() for left, right in zip(stamps, stamps[1:])]
    timing = ["first"]
    for interval in intervals:
        if interval <= 0:
            timing.append("non_increasing")
        elif interval < MIN_GAP.total_seconds():
            timing.append("short_interval")
        elif interval > MAX_GAP.total_seconds():
            timing.append("long_interval")
        else:
            timing.append("regular")
    rows, incidents = [], []
    for index, (row, stamp, flag) in enumerate(zip(readings, stamps, timing, strict=True)):
        context, phase = context_at(stamp, move_start, move_end, settled)
        uncertain = flag not in ("first", "regular") or index + 1 < len(timing) and timing[index + 1] in (
            "short_interval", "non_increasing")
        rows.append({"campaign_id": campaign, "reading_id": row["id"], "station_id": row["stationId"],
                     "session_id": row["sessionId"], "sequence": row["sequence"], "received_utc": row["receivedAt"],
                     "acquired_utc": row["acquiredAt"], "time_source": row["timeSource"], "origin": row["origin"],
                     **{column: row[sensor] for sensor, column in SENSORS.items()},
                     "quality_original": row["quality"], "issues_json": json.dumps(row["issues"], ensure_ascii=False),
                     "seconds_since_previous_receipt": intervals[index - 1] if index else None, "receipt_flag": flag,
                     "receipt_timing_uncertain": int(uncertain), "environment_observed": context, "phase": phase,
                     "rain_observation": "", "split_group": campaign, "ml_split": "unassigned_pilot"})
        if flag not in ("first", "regular"):
            incidents.append({"previous_sequence": readings[index - 1]["sequence"], "sequence": row["sequence"],
                              "previous_receipt_utc": readings[index - 1]["receivedAt"], "receipt_utc": row["receivedAt"],
                              "interval_seconds": intervals[index - 1], "receipt_flag": flag})
    elapsed = (stamps[-1] - stamps[0]).total_seconds()
    phases = defaultdict(list)
    for row, original in zip(rows, readings, strict=True):
        phases[row["phase"]].append(original)
    ids, sequences, times = (Counter(row[key] for row in readings) for key in ("id", "sequence", "receivedAt"))
    values = Counter(tuple(row[key] for key in SENSORS) for row in readings)
    counts = {"rows": len(rows), "start_utc": rows[0]["received_utc"], "end_utc": rows[-1]["received_utc"],
              "elapsed_seconds": elapsed, "effective_hz": (len(rows) - 1) / elapsed if elapsed > 0 else None,
              "median_interval_seconds": median(intervals) if intervals else None,
              "quality_original": Counter(row["quality"] for row in readings), "receipt_flags": Counter(timing),
              "time_sources": Counter(row["timeSource"] for row in readings),
              "missing_sequences_inside": max(sequences) - min(sequences) + 1 - len(sequences),
              "duplicate_ids": sum(n - 1 for n in ids.values()), "duplicate_sequences": sum(n - 1 for n in sequences.values()),
              "repeated_receipt_timestamps": sum(n - 1 for n in times.values()),
              "repeated_value_triplets_beyond_first": sum(n - 1 for n in values.values()),
              "measurements": summaries(readings),
              "by_phase": {phase: {"rows": len(group), "quality": Counter(row["quality"] for row in group),
                                   "measurements": summaries(group)} for phase, group in phases.items()}}
    return rows, incidents, counts


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--station", required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--move-at", required=True, type=utc)
    parser.add_argument("--move-uncertainty-min", required=True, type=int)
    parser.add_argument("--settled-from", required=True, type=utc)
    args = parser.parse_args()
    uncertainty = timedelta(minutes=args.move_uncertainty_min)
    move_start, move_end = args.move_at - uncertainty, args.move_at + uncertainty
    if not move_start < move_end < args.settled_from:
        parser.error("La banda del traslado debe terminar antes del punto de estabilización.")

    _, _, records = read_snapshot(args.db)
    selected = [row for row, ingested in records if ingested and row["stationId"] == args.station
                and row["sessionId"] == args.session and row["origin"] == "USB" and row["dataKind"] == "REAL"]
    if not selected or not utc(selected[0]["receivedAt"]) <= move_start < args.settled_from <= utc(selected[-1]["receivedAt"]):
        parser.error("Sesión de USB real ausente o límites fuera de la campaña seleccionada.")
    rows, incidents, report = derive(selected, args.campaign, move_start, move_end, args.settled_from)
    evidence = {path.name: digest(path) for path in sorted(args.evidence.iterdir()) if path.is_file()}
    if "Observaciones.txt" not in evidence:
        parser.error("Falta Observaciones.txt como fuente del contexto experimental.")
    report |= {"schema": "agroedge.usb-observational.v1", "campaign": args.campaign, "station": args.station,
               "session": args.session, "observed_move_utc": args.move_at.isoformat(),
               "move_uncertainty_minutes": args.move_uncertainty_min, "provisional_settling_end_utc": args.settled_from.isoformat(),
               "regular_receipt_interval_seconds": [MIN_GAP.seconds, MAX_GAP.seconds], "independent_rain_labels": 0,
               "split_group": args.campaign, "ml_split": "unassigned_pilot", "sqlite_sha256": digest(args.db),
               "original_files_sha256": evidence}
    with TemporaryDirectory(dir=args.out_dir.parent) as stage:
        pending = Path(stage) / args.out_dir.name
        pending.mkdir()
        write_csv(pending / "mediciones.csv", rows, rows[0].keys())
        write_csv(pending / "intervalos-irregulares.csv", incidents,
                  ("previous_sequence", "sequence", "previous_receipt_utc", "receipt_utc", "interval_seconds", "receipt_flag"))
        (pending / "resumen.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sums = "".join(f"{digest(file)}  {file.name}\n" for file in sorted(pending.iterdir()))
        (pending / "SHA256SUMS.txt").write_text(sums, encoding="ascii")
        pending.rename(args.out_dir)
    print(args.out_dir)


if __name__ == "__main__":
    main()

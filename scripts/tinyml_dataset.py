"""Prepare and train the precipitation feasibility model from annotated USB sessions."""

import argparse
from collections import Counter, defaultdict, deque
import csv
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import math
from pathlib import Path
import sqlite3
import statistics
from tempfile import TemporaryDirectory


LABELS = ("no_rain", "rain")
DEVICE_LABELS = ("Patrón sin lluvia observada", "Patrón con lluvia observada")
PARTITIONS = ("train", "validation", "test")
WINDOW = 6
MAX_GAP = timedelta(seconds=8)
EMBARGO = timedelta(minutes=30)
MIN_PER_CLASS = 10
MIN_EVENTS_PER_CLASS = 2


def utc(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"Fecha sin zona horaria: {value}")
    return dt.astimezone(timezone.utc)


def readings(path, station):
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return [json.loads(row[0]) for row in db.execute(
            "SELECT payload FROM real_readings WHERE origin='USB' AND station=? AND fingerprint IS NOT NULL "
            "ORDER BY session,seq", (station,))]
    finally:
        db.close()


def annotations(content):
    sessions = defaultdict(list)
    with io.StringIO(content.decode("utf-8-sig"), newline="") as file:
        for row in csv.DictReader(file):
            start, end = utc(row["start"]), utc(row["end"])
            if (end <= start or row["label"] not in LABELS or
                    any(not (row.get(k) or "").strip() for k in ("session", "event", "observer", "evidence"))):
                raise ValueError(f"Anotación inválida para {row.get('session')}")
            sessions[row["session"]].append((start, end, row))
    for entries in sessions.values():
        entries.sort(key=lambda entry: entry[0])
        if any(left[1] > right[0] for left, right in zip(entries, entries[1:])):
            raise ValueError("Hay intervalos de observación solapados en una sesión.")
    return sessions


def features(window):
    # Same units and offsets as classifier.h. Delta is in 0.05 hPa ticks.
    return (statistics.mean(r["temperature"] for r in window) - 20,
            statistics.mean(r["humidity"] for r in window) - 50,
            20 * (window[-1]["pressure"] - window[0]["pressure"]))


def windows(rows, periods, train_end, validation_end):
    sessions = defaultdict(list)
    for row in rows:
        sessions[row["sessionId"]].append(row)
    if periods.keys() - sessions.keys():
        raise ValueError("Hay anotaciones para sesiones USB ausentes en esta estación.")
    result = {split: [] for split in PARTITIONS}
    event_splits = {}
    for session, group in sessions.items():
        times = [utc(row["acquiredAt"]) for row in group]
        first, last = min(times), max(times)
        if last < train_end:
            split = "train"
        elif first >= train_end + EMBARGO and last < validation_end:
            split = "validation"
        elif first >= validation_end + EMBARGO:
            split = "test"
        else:
            continue
        intervals = iter(periods.get(session, ()))
        label = next(intervals, None)
        recent = deque(maxlen=WINDOW)
        previous, seq = None, None
        for row, stamp in zip(group, times):
            if previous is not None and (not timedelta(0) < stamp - previous <= MAX_GAP or row["sequence"] != seq + 1):
                recent.clear()
            previous, seq = stamp, row["sequence"]
            if row["quality"] != "VALID":
                recent.clear()
                continue
            recent.append((row, stamp))
            while label and stamp >= label[1]:
                label = next(intervals, None)
            if len(recent) < WINDOW or not label or recent[0][1] < label[0]:
                continue
            entry = label[2]
            event = entry["event"]
            if event_splits.setdefault(event, split) != split:
                raise ValueError(f"El evento {event} aparece en más de una partición.")
            result[split].append({"session": session, "event": event, "label": entry["label"],
                                  "ids": [sample[0]["id"] for sample in recent],
                                  "features": features([sample[0] for sample in recent])})
            recent.clear()  # Evaluation windows share no sensor rows.
    return result


def quantize(value):
    # Round halves away from zero and tolerate floating-point error at decimal ties.
    magnitude = math.floor(round(abs(value), 9) + 0.5)
    return max(-128, min(127, magnitude if value >= 0 else -magnitude))


def predict(vector, centroids):
    return min(range(len(centroids)), key=lambda i: math.dist(vector, centroids[i]))


def metrics(rows, predictions):
    matrix = [[0] * len(LABELS) for _ in LABELS]
    for row, prediction in zip(rows, predictions, strict=True):
        matrix[LABELS.index(row["label"])][prediction] += 1
    classes = {}
    for i, label in enumerate(LABELS):
        tp, actual = matrix[i][i], sum(matrix[i])
        predicted = sum(row[i] for row in matrix)
        classes[label] = {"precision": tp / predicted if predicted else None, "recall": tp / actual,
                          "f1": 2 * tp / (predicted + actual), "support": actual}
    return {"confusion": matrix, "by_class": classes, "accuracy": sum(matrix[i][i] for i in range(len(LABELS))) / len(rows),
            "macro_f1": statistics.mean(value["f1"] for value in classes.values())}


def model_header(version, quantized):
    values = ", ".join("{" + ", ".join(map(str, vector)) + "}" for vector in quantized)
    labels = ", ".join(json.dumps(label) for label in DEVICE_LABELS)
    return (f'#pragma once\n\n#include "classifier.h"\n\nnamespace agroedge {{\n\n'
            f'constexpr char modelVersion[] = "{version}";\nconstexpr char modelStatus[] = "TRAINED";\n'
            f'constexpr char labelText[][32] = {{{labels}}};\nconstexpr Features centroids[] = {{{values}}};\n\n'
            '}  // namespace agroedge\n')


def train(splits):
    counts = {split: dict(Counter(row["label"] for row in group)) for split, group in splits.items()}
    events = {split: {label: len({row["event"] for row in group if row["label"] == label}) for label in LABELS}
              for split, group in splits.items()}
    if any(counts[split].get(label, 0) < MIN_PER_CLASS or events[split][label] < MIN_EVENTS_PER_CLASS
           for split in PARTITIONS for label in LABELS):
        raise ValueError(f"Se necesitan {MIN_PER_CLASS} ventanas y {MIN_EVENTS_PER_CLASS} eventos por clase y partición. "
                         f"Ventanas disponibles: {counts}. Eventos disponibles: {events}.")
    train_rows = splits["train"]
    centroids = [tuple(map(statistics.mean, zip(*(row["features"] for row in train_rows if row["label"] == label))))
                 for label in LABELS]
    quantized = [tuple(map(quantize, vector)) for vector in centroids]
    majority = max(range(len(LABELS)), key=lambda i: counts["train"][LABELS[i]])
    summaries, vectors = {}, []
    for split in ("validation", "test"):
        rows = splits[split]
        integer_rows = [tuple(map(quantize, row["features"])) for row in rows]
        integer_predictions = [predict(vector, quantized) for vector in integer_rows]
        float_metrics = metrics(rows, (predict(row["features"], centroids) for row in rows))
        int8_metrics = metrics(rows, integer_predictions)
        summaries[split] = {"float": float_metrics, "int8": int8_metrics, "majority": metrics(rows, [majority] * len(rows)),
                            "int8_minus_float": {k: int8_metrics[k] - float_metrics[k] for k in ("accuracy", "macro_f1")}}
        if split == "test":
            vectors = [{"features": vector, "expected_index": prediction, "observed": row["label"], "ids": row["ids"]}
                       for row, vector, prediction in zip(rows, integer_rows, integer_predictions, strict=True)]
    return centroids, quantized, counts, events, summaries, vectors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/agroedge.sqlite"))
    parser.add_argument("--station", required=True)
    parser.add_argument("--labels", type=Path)
    parser.add_argument("--train-end", type=utc)
    parser.add_argument("--validation-end", type=utc)
    args = parser.parse_args()
    rows = readings(args.db, args.station)
    coverage = {"rows": len(rows), "sessions": sorted({row["sessionId"] for row in rows}),
                "quality": Counter(row["quality"] for row in rows)}
    print(json.dumps(coverage, ensure_ascii=False))
    if not args.labels:
        return
    if not args.train_end or not args.validation_end or args.train_end + EMBARGO >= args.validation_end:
        parser.error("Define ambos cortes cronológicos con un margen mayor de 30 minutos.")
    labels_bytes = args.labels.read_bytes()
    groups = windows(rows, annotations(labels_bytes), args.train_end, args.validation_end)
    centroids, quantized, counts, events, summary, vectors = train(groups)
    dataset = {"protocol": "precipitation-v1", "station": args.station, "label_order": LABELS,
               "cutoffs": [args.train_end.isoformat(), args.validation_end.isoformat()],
               "embargo_minutes": EMBARGO.seconds // 60, "annotation_sha256": hashlib.sha256(labels_bytes).hexdigest(),
               "readings_sha256": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest(), "partitions": groups}
    snapshot = json.dumps(dataset, ensure_ascii=False, indent=2)
    version = "precip-v1-" + hashlib.sha256(snapshot.encode()).hexdigest()[:16]
    out = Path("data/datasets") / version
    out.parent.mkdir(parents=True, exist_ok=True)
    files = {"dataset.json": snapshot, "model.h": model_header(version, quantized),
             "test-vectors.json": json.dumps({"version": version, "vectors": vectors}, indent=2),
             "evaluation.json": json.dumps({"centroids_float": centroids, "centroids_int8": quantized,
                                            "counts": counts, "events": events, "metrics": summary}, indent=2)}
    with TemporaryDirectory(dir=out.parent) as temporary:
        pending = Path(temporary) / version
        pending.mkdir()
        for name, content in files.items():
            (pending / name).write_text(content + "\n", encoding="utf-8")
        pending.rename(out)
    print(out)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, sqlite3.Error) as error:
        raise SystemExit(str(error)) from error

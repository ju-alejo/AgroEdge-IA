"""Create independent exposure labels and report usable windows for an audited campaign."""

import argparse
from collections import Counter
from datetime import timedelta
import json
from pathlib import Path

from scripts.process_usb_campaign import digest, write_csv
from scripts.tinyml_dataset import (EMBARGO, EXPOSURE_LABELS, PARTITIONS, WINDOW, annotations, label_coverage,
                                   readings, utc, windows)


def create_labels(audit, confirmation, rows):
    expected = dict(zip(("Entrenamiento", "Validacion", "Prueba"), PARTITIONS, strict=True))
    train, validation = [utc(value) for value in confirmation["cutoffs"]]
    output, details = [], []
    for session in audit["sessions"]:
        letter, session_id = session["letter"], session["session"]
        first, last = utc(session["start"]), utc(session["end"])
        phase = expected[session["partition"]]
        if not {"train": last < train, "validation": first >= train + EMBARGO and last < validation,
                "test": first >= validation + EMBARGO}[phase]:
            raise ValueError(f"La sesión completa {letter} no cabe en su partición cronológica.")
        record = confirmation["sessions"][letter]
        intervals = record["intervals"]
        if sorted(item[0] for item in intervals) != sorted(EXPOSURE_LABELS):
            raise ValueError(f"Las exposiciones confirmadas de {letter} no incluyen ambas clases.")
        session_rows = [row for row in rows if row["sessionId"] == session_id]
        for i, (label, observed_start, observed_end) in enumerate(intervals):
            start, end = utc(observed_start), utc(observed_end)
            usable = max(start, first + timedelta(minutes=10)) if i == 0 else start
            if not first <= usable < end <= last:
                raise ValueError(f"El intervalo de {letter}/{label} queda fuera de la captura o está vacío.")
            output.append({"session": session_id, "start": usable.isoformat(), "end": end.isoformat(), "label": label,
                           "event": letter, "observer": record["observer"], "evidence": record["evidence"]})
            counts = Counter(row["quality"] for row in session_rows if usable <= utc(row["acquiredAt"]) < end)
            details.append({"session": letter, "split": phase, "label": label, "observed_start": start.isoformat(),
                            "used_start": usable.isoformat(), "end": end.isoformat(), "labelled": sum(counts.values()),
                            "valid": counts["VALID"], "anomaly": counts["ANOMALY"]})
    return output, details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_dir", type=Path)
    parser.add_argument("confirmation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    audit_path = args.audit_dir / "auditoria.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    confirmation = json.loads(args.confirmation.read_text(encoding="utf-8-sig"))
    snapshot = Path(audit["snapshot"])
    if digest(snapshot) != audit["sha256"]:
        raise ValueError("El respaldo difiere de la auditoría.")
    ids = {row["session"] for row in audit["sessions"]}
    rows = [row for row in readings(snapshot, audit["station"]) if row["sessionId"] in ids]
    labels, details = create_labels(audit, confirmation, rows)
    args.output.mkdir()
    path = args.output / "etiquetas-exposicion.csv"
    write_csv(path, labels, list(labels[0]))
    groups = windows(rows, annotations(path.read_bytes(), EXPOSURE_LABELS), *map(utc, confirmation["cutoffs"]))
    for row in details:
        row["usable_windows"] = sum(w["event"] == row["session"] and w["label"] == row["label"] for w in groups[row["split"]])
        row["window_records"] = row["usable_windows"] * WINDOW
    counts, events, ready = label_coverage(groups, EXPOSURE_LABELS)
    result = {"cutoffs": confirmation["cutoffs"], "ready": ready, "windows": counts, "independent_events": events,
              "intervals": details, "audit_sha256": digest(audit_path), "confirmation_sha256": digest(args.confirmation),
              "labels_sha256": digest(path)}
    (args.output / "cobertura.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_csv(args.output / "cobertura.csv", details, list(details[0]))
    print(json.dumps({"ready": ready, "windows": counts, "independent_events": events}))


if __name__ == "__main__":
    main()

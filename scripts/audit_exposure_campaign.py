"""Audit the six field sessions captured on 2026-11-24 without writing to source files."""

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import csv
import json
from pathlib import Path
import sqlite3
import subprocess

from scripts.audit_usb_dataset import read_snapshot, summarize_session
from scripts.process_usb_campaign import digest, summaries, write_csv
from scripts.tinyml_dataset import MAX_GAP, MIN_GAP, utc


STATION = "TOCA-ESP32-01"
DAY = "2026-11-24"
EXPORTS = {
    "Entrenamiento": (("AB", "AgroEdge_USB_2026-11-24"),),
    "Validacion": (("C", "Validacion_Sesion_C"), ("D", "Validacion_Sesion_D")),
    "Prueba": (("E", "Prueba_Sesion_E"), ("F", "Prueba_Sesion_F")),
}


def backup(source, destination):
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)) as original:
        original.execute("PRAGMA query_only=ON")
        with destination.open("xb"):
            pass
        with closing(sqlite3.connect(destination)) as copy:
            original.backup(copy)
            copy.execute("PRAGMA journal_mode=DELETE")
            if copy.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                raise ValueError("El respaldo no pasó integrity_check.")


def audit(graph, letter, partition, group):
    result = summarize_session(group)
    rows = [row for row, _ in group]
    elapsed = (utc(result["end"]) - utc(result["start"])).total_seconds()
    result.update(letter=letter, partition=partition, elapsed_seconds=elapsed, effective_hz=(len(rows) - 1) / elapsed,
                  duplicate_ids=len(rows) - len({row["id"] for row in rows}),
                  duplicate_sequences=len(rows) - len({row["sequence"] for row in rows}),
                  repeated_receipt_timestamps=len(rows) - len({row["receivedAt"] for row in rows}),
                  announced_missing_before=sum(row["missingBefore"] for row in rows),
                  measurements=summaries(rows), issues=Counter(issue for row in rows for issue in row["issues"]))
    previous = None
    for row in rows:
        stamp = utc(row["receivedAt"])
        step = None if previous is None else (stamp - previous).total_seconds()
        graph.append({"session": letter, "partition": partition, "sequence": row["sequence"], "receipt": row["receivedAt"],
                      "elapsed_s": (stamp - utc(result["start"])).total_seconds(), "receipt_delta_s": step,
                      "unusual_interval": int(step is not None and not MIN_GAP.total_seconds() <= step <= MAX_GAP.total_seconds()),
                      "quality": row["quality"], "temperature_c": row["temperature"], "humidity_pct": row["humidity"],
                      "pressure_hpa": row["pressure"], "issues_json": json.dumps(row["issues"], ensure_ascii=False)})
        previous = stamp
    return result


def verify_exports(root, snapshot, groups, out):
    audits, graph, checks, seen, files = [], [], [], set(), []
    for partition, exports in EXPORTS.items():
        directory = root / f"{DAY}_{partition}"
        files.extend({"file": f"{directory.name}/{path.name}", "sha256": digest(path)}
                     for path in sorted(directory.iterdir()) if path.is_file())
        for letters, stem in exports:
            csv_path, excel_path = (directory / f"{stem}.{ext}" for ext in ("csv", "xlsx"))
            with csv_path.open(newline="", encoding="utf-8-sig") as file:
                ids = {row["Sesión"] for row in csv.DictReader(file, delimiter=";")}
            if len(ids) != len(letters) or ids - groups.keys() or ids & seen:
                raise ValueError(f"Sesiones inesperadas para {csv_path.name}: {sorted(ids)}.")
            ordered = sorted(ids, key=lambda id_: groups[id_][0][0]["acquiredAt"])
            seen.update(ordered)
            process = subprocess.run(["node", "--disable-warning=ExperimentalWarning", "scripts/verify-campaign-exports.mjs",
                                      str(snapshot), str(csv_path), str(excel_path), *ordered],
                                     check=True, capture_output=True, text=True, encoding="utf-8")
            checks.extend({"file": stem, **json.loads(line)} for line in process.stdout.splitlines())
            audits.extend(audit(graph, letter, partition, groups[id_]) for letter, id_ in zip(letters, ordered, strict=True))
    if sum(r["rows"] for r in audits if r["letter"] in "EF") != 884:
        raise ValueError("El total de prueba discrepa del total declarado (884).")
    write_csv(out / "series-auditadas.csv", graph, list(graph[0]))
    fields = ("letter", "partition", "session", "rows", "start", "end", "first_sequence", "last_sequence", "elapsed_seconds",
              "effective_hz", "duplicate_ids", "duplicate_sequences", "repeated_receipt_timestamps", "missing_sequences_inside",
              "announced_missing_before", "intervals_under_4_s", "intervals_over_8_s", "intervals_non_increasing")
    write_csv(out / "sesiones.csv", [{key: row[key] for key in fields} for row in audits], fields)
    return audits, checks, files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="SQLite original, abierta en modo de solo lectura")
    parser.add_argument("dataset_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--snapshot", type=Path, help="Reproducir con un respaldo consistente ya existente")
    args = parser.parse_args()
    args.output.mkdir()
    snapshot = args.snapshot or args.output / "agroedge-respaldo.sqlite"
    if args.snapshot is None:
        backup(args.source, snapshot)
    _, _, records = read_snapshot(snapshot)
    groups = defaultdict(list)
    for row, ingested in records:
        if row["stationId"] == STATION:
            groups[row["sessionId"]].append((row, ingested))
    audits, checks, files = verify_exports(args.dataset_root, snapshot, groups, args.output)
    payload = {"snapshot": str(snapshot), "sha256": digest(snapshot), "station": STATION, "sessions": audits,
               "reconciliation": checks, "source_files": files, "rows": sum(row["rows"] for row in audits),
               "by_partition": {partition: {"rows": sum(row["rows"] for row in audits if row["partition"] == partition),
                                             "quality": dict(sum((Counter(row["quality"]) for row in audits
                                                                 if row["partition"] == partition), Counter()))}
                                for partition in EXPORTS}}
    (args.output / "auditoria.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rows": payload["rows"], "partitions": payload["by_partition"]}))


if __name__ == "__main__":
    main()

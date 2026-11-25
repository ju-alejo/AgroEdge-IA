"""Plot observed sessions and quantify the C detector response without inferring labels."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import timedelta, timezone
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from scripts.tinyml_dataset import WINDOW, utc


BOGOTA = timezone(timedelta(hours=-5))
CHANNELS = {"temperature_c": "Temperatura (°C)", "humidity_pct": "Humedad relativa (%)", "pressure_hpa": "Presión (hPa)"}
COLORS = {"greenhouse": "#cde7cf", "outdoor": "#d2e7f5"}


def load_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def plot(group, labels, path):
    n = len(group)
    figure, panels = plt.subplots(3, n, figsize=(4.0 * n + 1.2, 8), sharex="col", squeeze=False, layout="constrained")
    for i, (session, rows) in enumerate(group.items()):
        times = [row["stamp"] for row in rows]
        marks = [k for k, row in enumerate(rows) if row["quality"] == "ANOMALY"]
        for j, (key, axis_label) in enumerate(CHANNELS.items()):
            ax = panels[j, i]
            values = [float(row[key]) if row[key] else float("nan") for row in rows]
            for label in labels[session]:
                ax.axvspan(utc(label["used_start"]), utc(label["end"]), color=COLORS[label["label"]], zorder=0)
            ax.plot(times, values, color="#173f59", linewidth=1)
            ax.scatter([times[k] for k in marks], [values[k] for k in marks], c="#b63827", s=8, zorder=3)
            if i == 0:
                ax.set_ylabel(axis_label)
            if j == 0:
                ax.set_title(f"Sesión {session}")
            ax.xaxis.set_major_locator(mdates.AutoDateLocator(tz=BOGOTA, minticks=3, maxticks=5))
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=BOGOTA))
            ax.grid(alpha=0.25, axis="y")
    figure.supxlabel("Hora de recepción en Bogotá · Invernadero en verde · Exterior en azul · ANOMALY en rojo")
    figure.savefig(path, dpi=170)
    plt.close(figure)


def incident(rows, labels):
    before, after = labels
    start = utc(before["end"])
    stop = utc(after["used_start"])
    transition = [row for row in rows if start <= row["stamp"] < stop]
    relevant = [row for row in rows if start <= row["stamp"] < utc(after["end"])]
    run, runs = [], []
    for row in relevant:
        if row["quality"] == "ANOMALY":
            run.append(row)
        elif run:
            runs.append(run)
            run = []
    if run:
        runs.append(run)
    flags = [{"first_utc": run[0]["receipt"], "last_utc": run[-1]["receipt"], "rows": len(run),
              "duration_between_flags_s": (run[-1]["stamp"] - run[0]["stamp"]).total_seconds(),
              "regime_renewals": [row["receipt"] for row in run if any("Se renovó la referencia" in issue
                                                                       for issue in json.loads(row["issues_json"]))]}
             for run in runs]
    first_valid_streak = []
    if runs:
        after_alarm = [row for row in relevant if row["stamp"] > runs[-1][-1]["stamp"]]
        for i in range(len(after_alarm) - WINDOW + 1):
            block = after_alarm[i:i + WINDOW]
            if all(row["quality"] == "VALID" and row["unusual_interval"] == "0" for row in block):
                first_valid_streak = block
                break
    return {"transition_bounds_utc": [start.isoformat(), stop.isoformat()], "transition_rows": len(transition),
            "quality_in_transition": Counter(row["quality"] for row in transition), "alarm_runs": flags,
            "first_six_consecutive_valid_after_last_alarm": [row["receipt"] for row in first_valid_streak or []],
            "transition_ranges": {key: [min(float(row[key]) for row in transition if row[key]),
                                        max(float(row[key]) for row in transition if row[key])] for key in CHANNELS},
            "outdoor_observation": after, "physical_recovery_exact_time": None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_dir", type=Path)
    args = parser.parse_args()
    sessions, labels = defaultdict(list), defaultdict(list)
    for row in load_csv(args.audit_dir / "series-auditadas.csv"):
        row["stamp"] = utc(row["receipt"])
        sessions[row["session"]].append(row)
    for label in load_csv(args.audit_dir / "etiquetado" / "cobertura.csv"):
        labels[label["session"]].append(label)
    for block, name in (("AB", "entrenamiento"), ("CD", "validacion"), ("EF", "prueba")):
        plot({key: sessions[key] for key in block}, labels, args.audit_dir / f"grafica-{name}.png")
    result = incident(sessions["C"], labels["C"])
    (args.audit_dir / "incidencia-C.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

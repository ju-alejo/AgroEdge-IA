"""Plot the campaign signals and detector flags against their receipt timestamps."""

import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as dates
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summary = json.loads((args.dataset / "resumen.json").read_text(encoding="utf-8"))
    with (args.dataset / "mediciones.csv").open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))

    bogota = timezone(timedelta(hours=-5))
    time = [datetime.fromisoformat(row["received_utc"]).astimezone(bogota) for row in rows]
    move = datetime.fromisoformat(summary["observed_move_utc"]).astimezone(bogota)
    settled = datetime.fromisoformat(summary["provisional_settling_end_utc"]).astimezone(bogota)
    changes = [datetime.fromisoformat(event["receipt_utc"]).astimezone(bogota) for event in summary["regime_changes"]]
    uncertain = [i for i, row in enumerate(rows) if row["receipt_timing_uncertain"] == "1"]
    palette = {"ink": "#213342", "muted": "#596874", "gap": "#cbd2d7", "shift": "#256047", "move": "#74472b"}
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": palette["ink"],
                         "axes.labelcolor": palette["ink"], "xtick.color": palette["muted"], "ytick.color": palette["muted"]})
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(11, 6.4), height_ratios=(2, 2, 1.35))
    fig.subplots_adjust(left=.18, right=.97, top=.84, bottom=.14, hspace=.28)
    fig.text(.18, .94, "Campaña 01 · Cambio de ambiente y alertas", size=18, weight="bold")
    fig.text(.18, .895, f"23 de noviembre de 2026  |  {len(rows):,} lecturas USB".replace(",", "."), color=palette["muted"])

    uncertain_set = set(uncertain)
    for ax, key, label, color in zip(axes[:2], ("temperature_c", "relative_humidity_pct"),
                                     ("Temperatura (°C)", "Humedad relativa (%)"), ("#006f79", "#315eaa"), strict=True):
        values = [float(r[key]) if r[key] else float("nan") for r in rows]
        ax.plot(time, [value if i not in uncertain_set else float("nan") for i, value in enumerate(values)],
                color=color, linewidth=1.2)
        ax.scatter([time[i] for i in uncertain], [values[i] for i in uncertain], s=4, color=palette["muted"], alpha=.35)
        ax.set_ylabel(label)

    alerts = axes[-1]
    for level, (selected, color) in enumerate((
            (uncertain, "#667985"),
            ([i for i, row in enumerate(rows) if row["quality_revised"] == "ANOMALY"], "#ae4d27"),
            ([i for i, row in enumerate(rows) if row["quality_original"] == "ANOMALY"], "#7253a1"))):
        alerts.scatter([time[i] for i in selected], [level] * len(selected), marker="|", s=65, color=color)
    alerts.set_yticks([0, 1, 2], labels=["Recepción incierta", "Regla v2", "Regla 0.2.1"])
    alerts.set_ylim(-.55, 2.55)
    alerts.set_xlabel("Hora de recepción en Bogotá (UTC−05:00)")
    alerts.xaxis.set_major_locator(dates.MinuteLocator(byminute=(0, 20, 40), tz=bogota))
    alerts.xaxis.set_major_formatter(dates.DateFormatter("%H:%M", tz=bogota))
    for ax in axes:
        ax.axvspan(move-timedelta(minutes=1), settled, color="#f3e8d5", zorder=0)
        ax.axvline(move, color=palette["move"], linewidth=.9, linestyle=":")
        for when in changes:
            ax.axvline(when, color=palette["shift"], linewidth=1, linestyle="--")
        ax.grid(axis="y", color="#e3e9ed", linewidth=.6)
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color(palette["gap"])
        ax.tick_params(axis="y", length=0)
    handles = [Line2D([], [], color=palette["move"], linestyle=":", label="Traslado hacia las 19:24"),
               Line2D([], [], color=palette["shift"], linestyle="--", label="Cambio confirmado por el detector"),
               Patch(facecolor="#f3e8d5", label="Banda de traslado y adaptación")]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(.17, .02), ncol=3, frameon=False, fontsize=8.8)
    with args.output.open("xb") as file:
        fig.savefig(file, format="png", dpi=170, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()

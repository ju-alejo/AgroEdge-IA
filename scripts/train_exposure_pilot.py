"""Fit the exposure pilot model using the independently observed contexts in campaign v2."""

import argparse
from collections import Counter
import csv
from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.tinyml_dataset import (EXPOSURE_DEVICE_LABELS, EXPOSURE_LABELS, MAX_GAP, MIN_GAP,
                                   WINDOW, features, fit_centroids, model_header, predict, quantize, utc)


PHASES = {"greenhouse": "before_move", "outdoor": "after_provisional_settling"}


def pilot_windows(rows):
    start = utc(rows[0]["received_utc"]) + timedelta(minutes=5)
    recent, windows = [], []
    previous = None
    for row in rows:
        label = row["environment_observed"]
        stamp, seq = utc(row["received_utc"]), int(row["sequence"])
        continuous = previous is None or (seq == previous[0] + 1 and MIN_GAP <= stamp - previous[1] <= MAX_GAP)
        previous = seq, stamp
        if not continuous or row["receipt_timing_uncertain"] != "0" or row["quality_revised"] != "VALID" or stamp < start:
            recent.clear()
            continue
        if PHASES.get(label) != row["phase"]:
            recent.clear()
            continue
        if recent and recent[-1]["label"] != label:
            recent.clear()
        recent.append({"id": row["reading_id"], "label": label, "temperature": float(row["temperature_c"]),
                       "humidity": float(row["relative_humidity_pct"]), "pressure": float(row["station_pressure_hpa"])})
        if len(recent) == WINDOW:
            windows.append({"label": label, "ids": [reading["id"] for reading in recent], "features": features(recent)})
            recent.clear()
    return windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    summary_bytes = (args.dataset / "resumen.json").read_bytes()
    summary = json.loads(summary_bytes)
    if summary.get("schema") != "agroedge.usb-observational.v2" or not summary.get("observed_move_utc"):
        raise ValueError("Se requiere el resumen v2 con el traslado observado en la bitácora.")
    sums = {name: digest for digest, name in (line.split("  ", 1) for line in
             (args.dataset / "SHA256SUMS.txt").read_text(encoding="ascii").splitlines())}
    csv_path = args.dataset / "mediciones.csv"
    data_hash = sha256(csv_path.read_bytes()).hexdigest()
    if sums.get(csv_path.name) != data_hash or sums.get("resumen.json") != sha256(summary_bytes).hexdigest():
        raise ValueError("La huella del CSV o del resumen v2 no coincide.")
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if (not rows or len(rows) != summary["rows"] or {row["origin"] for row in rows} != {"USB"}
            or {row["campaign_id"] for row in rows} != {summary["campaign"]}
            or {row["split_group"] for row in rows} != {summary["campaign"]}
            or {row["session_id"] for row in rows} != {rows[0]["session_id"]}):
        raise ValueError("El piloto requiere una sola campaña USB v2, con su sesión íntegra.")
    windows = pilot_windows(rows)
    counts = Counter(row["label"] for row in windows)
    if any(counts[label] < 10 for label in EXPOSURE_LABELS):
        raise ValueError(f"Cobertura insuficiente para ajustar los dos perfiles: {dict(counts)}")

    fit = fit_centroids(windows, EXPOSURE_LABELS)
    weights = [tuple(map(quantize, vector)) for vector in fit]
    if weights[0] == weights[1]:
        raise ValueError("La cuantización produjo centroides idénticos.")
    payload = {"protocol": "exposure-pilot-v1", "source_campaign": summary["campaign"], "source_csv_sha256": data_hash,
               "source_summary_sha256": sha256(summary_bytes).hexdigest(), "independent_sessions": 1,
               "label_order": EXPOSURE_LABELS, "label_source": "Observaciones.txt; metadatos de exposición y fase v2",
               "features": ["mean_temperature_c_minus_20", "mean_relative_humidity_pct_minus_50", "pressure_delta_hpa_times_20"],
               "counts": dict(counts), "centroids_float": fit, "centroids_int8": weights,
               "max_weight_rounding_error_ticks": max(abs(v - q) for values, integer in zip(fit, weights, strict=True)
                                                      for v, q in zip(values, integer, strict=True)),
               "scope": "fit_only", "validation": None, "test": None, "fit_windows": windows}
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    version = "exposure-pilot-" + sha256(serialized.encode()).hexdigest()[:12]
    vectors = []
    for label in EXPOSURE_LABELS:
        group = [row for row in windows if row["label"] == label]
        for row in (group[0], group[len(group) // 2], group[-1]):
            vector = tuple(map(quantize, row["features"]))
            vectors.append({"features": vector, "expected_index": predict(vector, weights), "ids": row["ids"]})

    with TemporaryDirectory(dir=args.output.parent) as stage:
        pending = Path(stage) / args.output.name
        pending.mkdir()
        files = {"model.h": model_header(version, weights, EXPOSURE_DEVICE_LABELS, "PRELIMINARY"),
                 "fit.json": serialized,
                 "paridad-dispositivo.json": json.dumps({"version": version, "purpose": "firmware_parity_from_fit_only",
                                                        "vectors": vectors}, indent=2) + "\n"}
        for name, content in files.items():
            (pending / name).write_bytes(content.encode("utf-8"))
        (pending / "SHA256SUMS.txt").write_text("".join(f"{sha256(content.encode()).hexdigest()}  {name}\n"
                                                      for name, content in files.items()), encoding="ascii")
        pending.rename(args.output)
    print(json.dumps({"version": version, "windows": dict(counts), "weights": weights, "validation": None}))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        raise SystemExit(str(error)) from error

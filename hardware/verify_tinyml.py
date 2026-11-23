"""Collect the ESP32-S3 benchmark and optionally replay held-out feature vectors."""

import argparse
import json
from pathlib import Path
import time

import serial


def exchange(device, command, event):
    device.write((command + "\n").encode("ascii"))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            row = json.loads(device.readline(4096))
        except (ValueError, UnicodeError):
            continue
        if isinstance(row, dict) and row.get("event") == event:
            return row
    raise TimeoutError(f"El dispositivo no respondió al comando {event}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.vectors.read_text(encoding="utf-8")) if args.vectors else None
    report = {}
    with serial.Serial(args.port, 115200, timeout=0.25, write_timeout=2) as device:
        time.sleep(2)
        device.reset_input_buffer()
        benchmark = exchange(device, "B", "benchmark")
        report["benchmark"] = benchmark
        if benchmark["runs"] < 100:
            raise ValueError("Se esperaban al menos 100 ejecuciones de la inferencia.")
        mhz = benchmark["cpuMHz"]
        report["derived"] = {"latency_us_from_cycles_mean": benchmark["cyclesMean"] / mhz,
                             "latency_us_from_cycles_std": benchmark["cyclesStd"] / mhz,
                             "throughput_per_s_with_benchmark_overhead": benchmark["runs"] * 1e6 / benchmark["batchUs"],
                             "sketch_pct_flash": benchmark["sketchBytes"] * 100 / benchmark["flashBytes"],
                             "sketch_pct_partition": benchmark["sketchBytes"] * 100 / benchmark["appPartitionBytes"],
                             "internal_heap_peak_pct": 100 * (1 - benchmark["heapInternalMin"] / benchmark["heapInternalTotal"])}
        if data:
            if benchmark["modelVersion"] != data["version"]:
                raise ValueError("La versión cargada en el dispositivo difiere de los vectores de evaluación.")
            predictions = []
            for vector in data["vectors"]:
                features = vector["features"]
                if len(features) != 3 or any(type(v) is not int or not -128 <= v <= 127 for v in features):
                    raise ValueError("Vector int8 incompatible.")
                response = exchange(device, "Q " + " ".join(map(str, features)), "prediction")
                if response["features"] != features or response["modelVersion"] != data["version"]:
                    raise ValueError("El dispositivo devolvió un vector o versión distinto.")
                predictions.append({**vector, "device_index": response["index"]})
            report["replay"] = {"predictions": predictions,
                                "mismatches": sum(row["device_index"] != row["expected_index"] for row in predictions)}
    with args.out.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(args.out)
    if report.get("replay", {}).get("mismatches"):
        raise SystemExit("Las predicciones del dispositivo difieren del modelo de referencia int8.")


if __name__ == "__main__":
    main()

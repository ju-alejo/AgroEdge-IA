"""Collect the ESP32-S3 benchmark and optionally replay feature vectors for device parity."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time


SENSOR_RANGES = {"temperature": (-40, 85), "humidity": (0, 100), "pressure": (300, 1100)}


def read_record(device):
    try:
        row = json.loads(device.readline(4096))
    except (ValueError, UnicodeError):
        return None
    return row if isinstance(row, dict) else None


def exchange(device, command, event):
    device.write((command + "\n").encode("ascii"))
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        row = read_record(device)
        if row and row.get("event") == event:
            return row
    raise TimeoutError(f"El dispositivo no respondió al comando {event}.")


def benchmark_metrics(report, expected_version=None):
    if expected_version and report.get("modelVersion") != expected_version:
        raise ValueError("La versión cargada en el dispositivo difiere de la esperada.")
    if report.get("runs") != 256 or report.get("warmup") != 16:
        raise ValueError("Se esperaban 256 inferencias medidas después de 16 ejecuciones de calentamiento.")
    if report.get("failedInvocations", 0) != 0:
        raise ValueError("El firmware reportó invocaciones fallidas en el benchmark.")
    if report.get("backend") == "TFLITE_MICRO" and not (
            type(report.get("modelBytes")) is int and report["modelBytes"] > 0
            and type(report.get("tensorArenaUsedBytes")) is int and type(report.get("tensorArenaBytes")) is int
            and 0 < report["tensorArenaUsedBytes"] <= report["tensorArenaBytes"]):
        raise ValueError("Memoria de TFLite Micro inválida.")
    positive = ("cpuMHz", "batchUs", "flashBytes", "appPartitionBytes", "sketchBytes", "heapInternalTotal")
    nonnegative = ("cyclesMean", "cyclesStd", "cyclesMax", "heapInternalMin", "heapInternalFree", "stackFreeMin",
                   "psramTotal", "psramFree", "weightsBytes", "windowBytes")
    for key in positive + nonnegative:
        value = report.get(key)
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0 or (key in positive and value == 0):
            raise ValueError(f"Dato de benchmark inválido: {key}")
    if (report["cyclesMean"] > report["cyclesMax"] or report["heapInternalMin"] > report["heapInternalFree"]
            or report["heapInternalFree"] > report["heapInternalTotal"] or report["psramFree"] > report["psramTotal"]):
        raise ValueError("Los recursos del benchmark contradicen los totales informados.")
    if not report["sketchBytes"] <= report["appPartitionBytes"] <= report["flashBytes"]:
        raise ValueError("El binario o la partición exceden la Flash informada.")
    mhz = report["cpuMHz"]
    return {"latency_us_from_cycles_mean": report["cyclesMean"] / mhz,
            "latency_us_from_cycles_std": report["cyclesStd"] / mhz,
            "latency_us_from_cycles_max": report["cyclesMax"] / mhz,
            "throughput_per_s_with_benchmark_overhead": report["runs"] * 1e6 / report["batchUs"],
            "sketch_pct_flash": report["sketchBytes"] * 100 / report["flashBytes"],
            "sketch_pct_partition": report["sketchBytes"] * 100 / report["appPartitionBytes"],
            "internal_heap_peak_pct": 100 * (1 - report["heapInternalMin"] / report["heapInternalTotal"])}


def verify_stream(device, expected_version, consecutive_inferences=1):
    recent = []
    deadline = time.monotonic() + 50 + 5 * consecutive_inferences
    while time.monotonic() < deadline:
        row = read_record(device)
        if not row or row.get("schemaVersion") != 1:
            continue
        stamp = time.monotonic()
        seq, station, session = row.get("sequence"), row.get("stationId"), row.get("sessionId")
        if type(seq) is not int or seq < 1 or not isinstance(station, str) or not isinstance(session, str) or not station or not session:
            recent.clear()
            continue
        if not all(type(row.get(key)) in (int, float) and lo <= row[key] <= hi for key, (lo, hi) in SENSOR_RANGES.items()):
            recent.clear()
            continue
        if recent:
            last, previous = recent[-1]
            if seq != last["sequence"] + 1 or (station, session) != (last["stationId"], last["sessionId"]) or stamp - previous > 8:
                recent.clear()
        recent.append((row, stamp))
        recent = recent[-6:]
        if len(recent) < 6:
            continue
        results = [sample.get("classification") for sample, _ in recent[-consecutive_inferences:]]
        if not all(isinstance(result, dict) and result.get("state") == "OK" for result in results):
            continue
        for result in results:
            score, label = result.get("score"), result.get("label")
            if (result.get("source") != "ESP32" or result.get("modelVersion") != expected_version or
                    result.get("modelStatus") not in ("PRELIMINARY", "TRAINED") or not isinstance(label, str) or not label.strip() or
                    type(score) not in (float, int) or not 0 <= score <= 1 or
                    type(result.get("inferenceUs")) is not int or result["inferenceUs"] < 0):
                raise ValueError("Inferencia ESP32 sin clase, puntuación, versión esperada o latencia válidas.")
        return {"confirmed_at": datetime.now(timezone.utc).isoformat(), "samples": [sample for sample, _ in recent]}
    raise TimeoutError("No se verificaron seis lecturas físicas consecutivas con clasificación.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--vectors", type=Path)
    parser.add_argument("--expect-model", help="Versión esperada del firmware en ejecución")
    parser.add_argument("--check-stream", action="store_true", help="Comprueba seis mediciones consecutivas antes del benchmark")
    parser.add_argument("--stream-inferences", type=int, choices=range(1, 7), default=1,
                        help="Cantidad de las últimas seis lecturas que deben tener inferencia consecutiva")
    parser.add_argument("--expect-backend", choices=("TFLITE_MICRO", "CENTROIDS"))
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    data = json.loads(args.vectors.read_text(encoding="utf-8")) if args.vectors else None
    expected_version = data["version"] if data else args.expect_model
    if args.expect_model and expected_version != args.expect_model:
        parser.error("--expect-model difiere de la versión de los vectores.")
    if args.check_stream and not expected_version:
        parser.error("--check-stream requiere conocer la versión esperada con --expect-model o --vectors.")
    if args.out.exists() or not args.out.parent.is_dir():
        parser.error("La salida debe ser un archivo nuevo en un directorio existente.")
    import serial

    report = {}
    with serial.Serial(args.port, 115200, timeout=0.25, write_timeout=2) as device:
        time.sleep(2)
        device.reset_input_buffer()
        if args.check_stream:
            report["measurement_check"] = verify_stream(device, expected_version, args.stream_inferences)
        benchmark = exchange(device, "B", "benchmark")
        if args.expect_backend and benchmark.get("backend") != args.expect_backend:
            raise ValueError("El dispositivo no ejecutó el intérprete esperado.")
        report["benchmark"] = benchmark
        report["derived"] = benchmark_metrics(benchmark, expected_version)
        if data:
            predictions = []
            for vector in data["vectors"]:
                features = vector["features"]
                if len(features) != 3 or any(type(v) is not int or not -128 <= v <= 127 for v in features):
                    raise ValueError("Vector int8 incompatible.")
                response = exchange(device, "Q " + " ".join(map(str, features)), "prediction")
                if response["features"] != features or response["modelVersion"] != data["version"]:
                    raise ValueError("El dispositivo devolvió un vector o versión distinto.")
                prediction = {**vector, "device_index": response["index"]}
                if "expected_logit_int8" in vector:
                    prediction["device_logit_int8"] = response["logitInt8"]
                predictions.append(prediction)
            report["replay"] = {"purpose": data.get("purpose", "held_out_vectors"), "predictions": predictions,
                                "mismatches": sum(row["device_index"] != row["expected_index"] for row in predictions),
                                "logit_mismatches": sum(row.get("device_logit_int8") != row.get("expected_logit_int8")
                                                        for row in predictions)}
    with args.out.open("x", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write("\n")
    print(args.out)
    if any(report.get("replay", {}).get(key) for key in ("mismatches", "logit_mismatches")):
        raise SystemExit("Las predicciones del dispositivo difieren del modelo de referencia int8.")


if __name__ == "__main__":
    main()

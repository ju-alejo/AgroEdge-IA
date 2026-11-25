"""Fit on two USB sessions, select on validation, and freeze TensorFlow Lite before testing."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as schema

from scripts.process_usb_campaign import digest, write_csv
from scripts.tinyml_dataset import (EXPOSURE_DEVICE_LABELS, EXPOSURE_LABELS, annotations, fit_centroids,
                                   label_coverage, metrics, predict, quantize, readings, utc, windows)


def as_int8_features(rows):
    return np.asarray([list(map(quantize, row["features"])) for row in rows], dtype=np.float32)


def fit(rows):
    centroids = np.asarray(fit_centroids(rows, EXPOSURE_LABELS), dtype=np.float32)
    delta = centroids[1] - centroids[0]
    halfway = centroids.mean(axis=0)
    humidity = delta * np.array([0, 1, 0], dtype=np.float32)
    x = np.asarray([row["features"] for row in rows], dtype=np.float32)
    y = np.array([1 if row["label"] == "outdoor" else -1 for row in rows], dtype=np.float32)
    center, spread = x.mean(axis=0), np.maximum(x.std(axis=0), 1)
    z = (x - center) / spread
    ridge = np.linalg.solve(z.T @ z + np.eye(3) * (0.1 * len(rows)), z.T @ (y - y.mean())) / spread
    return centroids, {"humidity": (humidity, -float(humidity @ halfway)),
                       "centroid": (delta, -float(delta @ halfway)),
                       "ridge": (ridge, float(y.mean() - center @ ridge))}


def convert(weights, bias, representative=None):
    module = tf.Module()

    @tf.function(input_signature=[tf.TensorSpec((1, 3), tf.float32, name="sensor_features")], autograph=False)
    def logits(value):
        layer = tf.linalg.matmul(value, tf.constant(np.asarray(weights, dtype=np.float32).reshape(3, 1)))
        return tf.nn.bias_add(layer, tf.constant([bias], dtype=tf.float32))

    converter = tf.lite.TFLiteConverter.from_concrete_functions([logits.get_concrete_function()], module)
    if representative is not None:
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        converter.representative_dataset = lambda: ([sample.reshape(1, 3)] for sample in representative)
        converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
        converter.inference_input_type = converter.inference_output_type = tf.int8
    return converter.convert()


def half_away(value):
    return np.copysign(np.floor(np.abs(value) + 0.5), value)


class Interpreter:
    def __init__(self, model, integer):
        graph = schema.Model.GetRootAsModel(model, 0)
        if (graph.Version() != 3 or graph.SubgraphsLength() != 1 or graph.Subgraphs(0).OperatorsLength() != 1
                or graph.OperatorCodes(0).BuiltinCode() != schema.BuiltinOperator.FULLY_CONNECTED):
            raise ValueError("Se esperaba un solo operador FULLY_CONNECTED compatible con Micro.")
        self.opcode_version = graph.OperatorCodes(0).Version()
        self.integer = integer
        self.runner = tf.lite.Interpreter(model_content=model, num_threads=1,
                                          experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF)
        self.runner.allocate_tensors()
        self.input, self.output = self.runner.get_input_details()[0], self.runner.get_output_details()[0]
        expected = np.int8 if integer else np.float32
        if self.input["dtype"] != expected or self.output["dtype"] != expected:
            raise ValueError("Tipo inesperado en los tensores de entrada o salida.")

    def raw_codes(self, inputs):
        scale, zero = self.input["quantization"]
        return half_away(inputs / np.float32(scale)) + zero

    def infer(self, inputs):
        if self.integer:
            raw = self.raw_codes(inputs)
            saturation = int(np.count_nonzero((raw < -128) | (raw > 127)))
            values = np.clip(raw, -128, 127).astype(np.int8)
        else:
            values, saturation = inputs, 0
        outputs = []
        for value in values:
            self.runner.set_tensor(self.input["index"], value.reshape(1, 3))
            self.runner.invoke()
            outputs.append(self.runner.get_tensor(self.output["index"]).item())
        cutoff = self.output["quantization"][1] if self.integer else 0
        return [int(output > cutoff) for output in outputs], outputs, saturation

    def metadata(self):
        return {"input": self.input["quantization"], "output": self.output["quantization"],
                "operator": "FULLY_CONNECTED", "operator_version": self.opcode_version}


def evaluate(rows, candidates, centroids, majority):
    floats = np.asarray([row["features"] for row in rows], dtype=np.float32)
    integers = as_int8_features(rows)
    result = {"majority": metrics(rows, [majority] * len(rows), EXPOSURE_LABELS),
              "centroid_manual_int8": metrics(rows, (predict(v, [tuple(map(quantize, c)) for c in centroids])
                                                     for v in integers), EXPOSURE_LABELS)}
    outputs = {}
    for name, (floating, integer) in candidates.items():
        baseline, _, _ = floating.infer(floats)
        predictions, logits, clipped = integer.infer(integers)
        raw, converted = (metrics(rows, group, EXPOSURE_LABELS) for group in (baseline, predictions))
        result[name] = {"float": raw, "int8": converted, "clipped_input_components": clipped,
                        "class_changes": sum(a != b for a, b in zip(baseline, predictions, strict=True)),
                        "int8_minus_float": {key: converted[key] - raw[key] for key in ("accuracy", "balanced_accuracy", "macro_f1")}}
        outputs[name] = (predictions, logits)
    return result, outputs


def header(model, version):
    body = "\n".join("  " + ", ".join(f"0x{b:02x}" for b in model[i:i + 12]) + "," for i in range(0, len(model), 12))
    labels = ", ".join(json.dumps(label) for label in EXPOSURE_DEVICE_LABELS)
    return (f'#pragma once\n\n#include <stdint.h>\n\nnamespace agroedge {{\n'
            f'constexpr char modelVersion[] = "{version}";\nconstexpr char modelStatus[] = "TRAINED";\n'
            f'constexpr char labelText[][32] = {{{labels}}};\n'
            f'alignas(16) inline constexpr uint8_t modelFlatbuffer[] = {{\n{body}\n}};\n}}\n')


def write_json(path, value):
    with path.open("x", encoding="utf-8") as file:
        json.dump(value, file, indent=2, ensure_ascii=False)
        file.write("\n")


def saturation_diagnostic(interpreter, vectors):
    units = ("temperature", "humidity", "pressure_delta")
    scale, zero = interpreter.input["quantization"]
    features = np.asarray([row["features"] for row in vectors], dtype=np.float32)
    raw = interpreter.raw_codes(features)
    cases = []
    for row, flags in zip(vectors, (raw < -128) | (raw > 127), strict=True):
        clipped = [name for name, flag in zip(units, flags, strict=True) if flag]
        if clipped:
            cases.append({"event": row["event"], "label": row["observed"], "input": row["features"], "clipped": clipped})
    return {"real_feature_limits": [(bound - zero) * scale for bound in (-128, 127)],
            "clipped_components_by_sensor": Counter(name for row in cases for name in row["clipped"]),
            "clipped_components_by_class": Counter(row["label"] for row in cases for _ in row["clipped"]),
            "windows_affected": len(cases), "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit", type=Path)
    parser.add_argument("labels", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    audit = json.loads(args.audit.read_text(encoding="utf-8"))
    coverage = json.loads((args.labels.parent / "cobertura.json").read_text(encoding="utf-8"))
    db = Path(audit["snapshot"])
    if (digest(db) != audit["sha256"] or digest(args.audit) != coverage["audit_sha256"]
            or digest(args.labels) != coverage["labels_sha256"]):
        raise ValueError("Las huellas no concuerdan con la auditoría y el etiquetado.")
    rows = readings(db, audit["station"])
    sessions = {entry["session"] for entry in audit["sessions"]}
    dataset = windows([row for row in rows if row["sessionId"] in sessions], annotations(args.labels.read_bytes(), EXPOSURE_LABELS),
                      *map(utc, coverage["cutoffs"]))
    counts, events, ready = label_coverage(dataset, EXPOSURE_LABELS)
    if not ready:
        raise ValueError(f"Cobertura insuficiente: {counts}, {events}")
    args.output.mkdir()
    # Audit/test membership may be counted, but only training rows fit and calibrate the model.
    train = dataset["train"]
    centroids, coefficients = fit(train)
    representative = as_int8_features(train)
    majority = max(range(2), key=lambda i: counts["train"][EXPOSURE_LABELS[i]])
    models = {name: (convert(*param), convert(*param, representative=representative)) for name, param in coefficients.items()}
    candidates = {name: (Interpreter(floating, False), Interpreter(integer, True)) for name, (floating, integer) in models.items()}
    val, validation_predictions = evaluate(dataset["validation"], candidates, centroids, majority)
    selected = max(candidates, key=lambda name: (val[name]["int8"]["balanced_accuracy"], val[name]["int8"]["macro_f1"]))
    floating, integer = models[selected]
    version = "exposure-tflm-" + sha256(integer).hexdigest()[:12]
    (args.output / "exposure-int8.tflite").write_bytes(integer)
    (args.output / "exposure-float.tflite").write_bytes(floating)
    (args.output / "tflm_model_data.h").write_text(header(integer, version), encoding="utf-8")
    frozen = {"version": version, "selected": selected, "selection_rule": "validation int8 balanced accuracy then macro F1 then model order",
              "candidate_order": list(candidates), "validation": val, "tensorflow": tf.__version__, "counts": counts, "events": events,
              "calibration_rows": len(train), "int8": candidates[selected][1].metadata(),
              "sha256_int8": sha256(integer).hexdigest(), "sha256_float": sha256(floating).hexdigest(),
              "size_bytes": {name: dict(zip(("float", "int8"), map(len, models[name]), strict=True)) for name in models},
              "fit": {name: {"weights": weights.tolist(), "bias": bias} for name, (weights, bias) in coefficients.items()},
              "centroids_float": centroids.tolist(), "audit_sha256": digest(args.audit), "labels_sha256": digest(args.labels),
              "label_order": EXPOSURE_LABELS}
    write_json(args.output / "modelo-congelado.json", frozen)
    val_counts = Counter((row["event"], row["label"], EXPOSURE_LABELS[predicted]) for row, predicted in
                         zip(dataset["validation"], validation_predictions[selected][0], strict=True))
    write_json(args.output / "validacion-por-sesion.json", [
        {"session": event, "observed": label, "predicted": guess, "windows": n}
        for (event, label, guess), n in sorted(val_counts.items())])

    test = dataset["test"]
    result, outputs = evaluate(test, {selected: candidates[selected]}, centroids, majority)
    # Keep the held-out predictions of the two fixed baselines without opening test for candidate selection.
    humidity_pair = candidates["humidity"]
    humidity_test, _ = evaluate(test, {"humidity": humidity_pair}, centroids, majority)
    result["humidity"] = humidity_test["humidity"]
    predictions, logits = outputs[selected]
    write_json(args.output / "evaluacion-prueba.json", {"frozen_sha256": digest(args.output / "modelo-congelado.json"), "metrics": result})
    vectors = [{"features": [int(x) for x in vector], "expected_index": predicted, "expected_logit_int8": logit,
                "observed": row["label"], "event": row["event"], "ids": row["ids"]}
               for row, vector, predicted, logit in zip(test, as_int8_features(test), predictions, logits, strict=True)]
    write_json(args.output / "test-vectors.json", {"version": version, "purpose": "held_out_tflite_int8_vectors", "vectors": vectors})
    write_json(args.output / "diagnostico-saturacion-prueba.json", saturation_diagnostic(candidates[selected][1], vectors))
    write_json(args.output / "ventanas.json", dataset)
    table = [{"split": part, "model": name, "representation": rep, **{k: score[k] for k in ("accuracy", "balanced_accuracy", "macro_f1")}}
             for part, results in (("validation", val), ("test", result)) for name, scores in results.items()
             for rep, score in ((("float", scores["float"]), ("int8", scores["int8"])) if "int8" in scores else (("baseline", scores),))]
    write_csv(args.output / "comparacion.csv", table, list(table[0]))
    print(json.dumps({"model": version, "selected": selected, "validation": val[selected], "test": result[selected]}))


if __name__ == "__main__":
    main()

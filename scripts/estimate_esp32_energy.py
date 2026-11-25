"""Estimate chip energy from official reference currents and a measured kernel latency."""

import argparse
import json
import math
from pathlib import Path


DATASHEET = "https://documentation.espressif.com/esp32_s3_datasheet_en.pdf"
CURRENTS_MA = {"one_core_32_bit": 65.9, "two_cores_32_bit": 81.3, "two_cores_128_bit": 107.9}
VOLTAGE = 3.3


def estimate(report):
    bench = report["benchmark"]
    latency = report["derived"]["latency_us_from_cycles_mean"]
    if bench["cpuMHz"] != 240 or type(latency) not in (float, int) or not math.isfinite(latency) or latency <= 0:
        raise ValueError("Se requiere una latencia de inferencia medida a 240 MHz.")
    micro = bench.get("backend") == "TFLITE_MICRO"
    latency_field = "measured_inference_latency_us" if micro else "measured_search_latency_us"
    energy_field = "energy_uj_per_inference" if micro else "energy_uj_per_class_search"
    scenarios = {name: {"current_ma": current, "power_mw": round(VOLTAGE * current, 2),
                        energy_field: round(VOLTAGE * current * latency / 1000, 6)}
                 for name, current in CURRENTS_MA.items()}
    return {"kind": "THEORETICAL_CHIP_ESTIMATE", "source": DATASHEET, "datasheet_version": "2.2", "tables": ["5-7", "5-9"],
            "model": bench["modelVersion"], "cpu_mhz": 240, "voltage_v": VOLTAGE, latency_field: latency,
            "timing_scope": "tflite_input_encoding_invoke_and_class" if micro else "centroid_class_search",
            "modem_sleep_peripheral_clocks_enabled": scenarios, "wifi_tx_peak_reference": {"current_ma": 340, "power_mw": 1122},
            "board_current_measured": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = estimate(json.loads(args.benchmark.read_text(encoding="utf-8-sig")))
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
        file.write("\n")
    print(args.output)


if __name__ == "__main__":
    main()

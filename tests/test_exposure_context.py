import sys
import unittest
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.enrich_open_meteo import align, parse_hours
from scripts.estimate_esp32_energy import estimate
from scripts.tinyml_dataset import EXPOSURE_LABELS, annotations
from scripts.train_exposure_pilot import pilot_windows

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper"))
import toca_forecast as toca


def forecast_html():
    def table(day):
        names = (*toca.FIELDS, "Cielo")
        cells = ("20,2", "—", "10", "4", "70", '<span class="f-cielo" title="Cubierto"></span>')
        rows = "".join(f"<tr><th>{name}</th>{f'<td>{cell}</td>' * 24}</tr>" for name, cell in zip(names, cells))
        header = "".join(f"<th>{hour:02}</th>" for hour in range(24))
        return f'<table class="tabla--calor"><thead><tr><th>{day}</th>{header}</tr></thead><tbody>{rows}</tbody></table>'

    return (f'<meta charset="utf-8"><link rel="canonical" href="{toca.URL}"><h1>El tiempo en Toca</h1>' + table("lun 23") + table("mar 24")
            + "<footer>Open-Meteo · CC BY 4.0</footer>").encode()


class ExposureContextTest(unittest.TestCase):
    def test_pilot_excludes_warmup_uncertain_transition_and_other_quality(self):
        start = datetime(2026, 11, 23, tzinfo=timezone.utc)
        rows = []
        for i in range(85):
            label, phase = ("greenhouse", "before_move") if i < 70 else ("outdoor", "after_provisional_settling")
            if i == 66:
                phase = "transition"
            rows.append({"reading_id": str(i), "sequence": str(i), "received_utc": (start + timedelta(seconds=5 * i)).isoformat(),
                         "environment_observed": label, "phase": phase, "receipt_timing_uncertain": "1" if i == 67 else "0",
                         "quality_revised": "ANOMALY" if i == 71 else "VALID", "temperature_c": "21", "relative_humidity_pct": "65",
                         "station_pressure_hpa": "736"})
        windows = pilot_windows(rows)
        self.assertEqual([w["ids"] for w in windows], [[str(i) for i in range(k, k + 6)] for k in (60, 72, 78)])
        self.assertEqual([w["label"] for w in windows], ["greenhouse", "outdoor", "outdoor"])
        self.assertEqual(windows[0]["features"], (1, 15, 0))

    def test_exposure_annotations_require_the_corresponding_target(self):
        raw = b"session,start,end,label,event,observer,evidence\nA,2026-11-24T07:10:00-05:00,2026-11-24T07:20:00-05:00,outdoor,E,O,V"
        with self.assertRaises(ValueError):
            annotations(raw)
        self.assertEqual(annotations(raw, EXPOSURE_LABELS)["A"][0][2]["label"], "outdoor")

    def test_weather_join_uses_completed_hours_and_retains_missing_values(self):
        end = int(datetime(2026, 11, 24, 1, tzinfo=timezone.utc).timestamp())
        hourly = {"hourly": {"time": [end, end + 3600], "precipitation_previous_day1": [None, 4]},
                  "hourly_units": {"precipitation_previous_day1": "mm"}}
        hours = parse_hours(hourly, "_previous_day1", ("precipitation",))
        stamped = {"reading_id": "A", "received_utc": "2026-11-24T01:58:00Z", "receipt_timing_uncertain": "0"}
        aligned = align(stamped, "previous_run_24h", hours)
        self.assertEqual(aligned["join_status"], "unavailable")
        self.assertEqual(aligned["nominal_forecast_cutoff_utc"], "2026-11-23T01:00:00+00:00")
        self.assertIsNone(aligned["precipitation"])
        self.assertEqual(aligned["use"], "retrospective_context_only")
        uncertain = align(stamped | {"receipt_timing_uncertain": "1"}, "previous_run_24h", hours)
        self.assertEqual(uncertain["join_status"], "receipt_uncertain")
        self.assertIsNone(uncertain["valid_hour_end_utc"])

    def test_toca_parser_checks_date_and_preserves_attribution_and_nulls(self):
        payload = forecast_html()
        fetched = datetime(2026, 11, 24, 2, tzinfo=timezone.utc)
        rows = toca.parse_forecast(payload, fetched)
        self.assertEqual((len(rows), rows[0]["validAt"], rows[-1]["validAt"]),
                         (48, "2026-11-23T05:00:00Z", "2026-11-25T04:00:00Z"))
        self.assertEqual((rows[0]["temperatureC"], rows[0]["sky"], rows[0]["precipitationMm"]), (20.2, "Cubierto", None))
        with self.assertRaisesRegex(ValueError, "Día u horas"):
            toca.parse_forecast(payload, fetched + timedelta(days=1))
        with self.assertRaisesRegex(ValueError, "atribución"):
            toca.parse_forecast(payload.replace(b"Open-Meteo", b"--"), fetched)

    def test_toca_gate_survives_reopening_and_runs_at_next_eligible_time(self):
        fetched = datetime(2026, 11, 24, 2, tzinfo=timezone.utc)
        with TemporaryDirectory() as tmp, patch.object(toca, "download", return_value=forecast_html()) as loader:
            directory = Path(tmp)
            with closing(toca.connect(directory)) as database:
                self.assertEqual(toca.fetch(database, fetched)["resultado"], "NUEVA")
            with closing(toca.connect(directory)) as database:
                self.assertEqual(toca.fetch(database, fetched + timedelta(minutes=5))["resultado"], "EN_ESPERA")
                self.assertEqual(loader.call_count, 1)
                loader.return_value = forecast_html().replace(b"mar 24", b"mi\xc3\xa9 25").replace(b"lun 23", b"mar 24")
                self.assertEqual(toca.fetch(database, fetched + timedelta(days=1))["resultado"], "NUEVA")
                self.assertEqual(loader.call_count, 2)
                self.assertEqual(database.execute("SELECT count(*) FROM snapshots").fetchone()[0], 2)

    def test_energy_is_theoretical_chip_power_times_kernel_latency(self):
        report = {"benchmark": {"cpuMHz": 240, "modelVersion": "fixture"}, "derived": {"latency_us_from_cycles_mean": 0.443}}
        result = estimate(report)
        chips = result["modem_sleep_peripheral_clocks_enabled"]
        self.assertEqual((chips["one_core_32_bit"]["power_mw"], chips["one_core_32_bit"]["energy_uj_per_class_search"]),
                         (217.47, 0.096339))
        self.assertFalse(result["board_current_measured"])
        self.assertEqual(result["wifi_tx_peak_reference"]["power_mw"], 1122)

from datetime import timedelta
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from hardware.verify_tinyml import benchmark_metrics, verify_stream
from scripts.audit_usb_dataset import read_snapshot, summarize_session
from scripts.audit_exposure_campaign import backup
from scripts.label_exposure_campaign import create_labels
from scripts.process_usb_campaign import derive
from scripts.tinyml_dataset import annotations, utc


class PhaseATest(unittest.TestCase):
    def test_processed_campaign_marks_transfer_and_preserves_unlabeled_measurements(self):
        start = utc("2026-11-23T18:00:00-05:00")
        records = []
        for i, offset in enumerate((0, 5, 500, 500.1, 510), start=1):
            stamp = (start + timedelta(seconds=offset)).isoformat()
            records.append({"id": f"qa-{i}", "stationId": "QA", "sessionId": "BOOT", "sequence": i,
                            "timeSource": "RECEIPT", "origin": "USB", "acquiredAt": stamp, "receivedAt": stamp,
                            "temperature": 20, "humidity": 80, "pressure": 736, "quality": "ANOMALY", "issues": []})
        rows, incidents, counts = derive(records, "qa-campaign", start + timedelta(seconds=5),
                                         start + timedelta(seconds=20), start + timedelta(seconds=505))
        self.assertEqual([r["phase"] for r in rows], ["before_move", "transfer", "settling", "settling",
                                                       "after_provisional_settling"])
        self.assertEqual([i["receipt_flag"] for i in incidents], ["long_interval", "short_interval", "long_interval"])
        self.assertEqual(counts["quality_original"], {"ANOMALY": 5})
        self.assertTrue(all(row["rain_observation"] == "" and row["split_group"] == "qa-campaign"
                            and row["ml_split"] == "unassigned_pilot" for row in rows))

    def test_read_only_path_does_not_create_a_database(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.sqlite"
            with self.assertRaises(sqlite3.OperationalError):
                read_snapshot(missing)
            self.assertFalse(missing.exists())

    def test_read_only_path_sees_committed_uncheckpointed_wal_rows(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sessions.sqlite"
            db = sqlite3.connect(path)
            try:
                db.executescript("PRAGMA journal_mode=WAL; PRAGMA wal_autocheckpoint=0;"
                                 "CREATE TABLE real_readings(origin, station, session, seq, payload, fingerprint);"
                                 "CREATE TABLE simulated_readings(origin);")
                db.execute("INSERT INTO real_readings VALUES('USB','QA','test',1,'{}','fixture')")
                db.commit()
                self.assertTrue(path.with_suffix(".sqlite-wal").exists())
                self.assertEqual(read_snapshot(path), ({"USB": 1}, 0, [({}, True)]))
                target = path.with_name("consistent.sqlite")
                backup(path, target)
                self.assertEqual(read_snapshot(target), ({"USB": 1}, 0, [({}, True)]))
                with self.assertRaises(FileExistsError):
                    backup(path, target)
            finally:
                db.close()

    def test_session_reports_gaps_disjoint_windows_and_first_edge_classification(self):
        start = utc("2026-11-23T14:00:00-05:00")
        serial_result = {"source": "ESP32", "state": "OK", "modelVersion": "qa-only", "inferenceUs": 1}
        rows = [({"acquiredAt": (start + timedelta(seconds=i * 5)).isoformat(), "stationId": "QA",
                  "sessionId": "boot-qa", "sequence": i, "timeSource": "RECEIPT", "temperature": 23,
                  "humidity": 63, "pressure": 736, "quality": "ANOMALY" if i == 9 else "VALID",
                  "classification": serial_result if i == 14 else None}, True)
                for i in list(range(1, 7)) + list(range(9, 15))]
        session = summarize_session(rows)
        self.assertEqual(session["missing_sequences_inside"], 2)
        self.assertEqual(session["consecutive_intervals_s"]["median"], 5)
        self.assertEqual(session["training_windows_before_labeling"], 1)
        self.assertEqual(session["first_classified_window"]["first_sequence"], 9)

    def test_benchmark_derivations_and_invalid_measurements(self):
        fixture = {"runs": 256, "warmup": 16, "modelVersion": "qa-only", "cpuMHz": 240, "batchUs": 1000,
                   "flashBytes": 16000, "appPartitionBytes": 1000, "sketchBytes": 400, "heapInternalTotal": 200,
                   "heapInternalFree": 120, "heapInternalMin": 100, "stackFreeMin": 60, "weightsBytes": 9,
                   "windowBytes": 60, "cyclesMean": 240, "cyclesStd": 48, "cyclesMax": 480, "psramTotal": 0, "psramFree": 0}
        result = benchmark_metrics(fixture, "qa-only")
        self.assertEqual(result["latency_us_from_cycles_mean"], 1)
        self.assertEqual(result["latency_us_from_cycles_max"], 2)
        self.assertEqual(result["sketch_pct_partition"], 40)
        for invalid in ({"cpuMHz": 0}, {"runs": 255}, {"cyclesMean": float("nan")}, {"heapInternalMin": 130}):
            with self.assertRaises(ValueError):
                benchmark_metrics({**fixture, **invalid}, "qa-only")
        with self.assertRaisesRegex(ValueError, "versión"):
            benchmark_metrics(fixture, "different-model")
        micro = {**fixture, "backend": "TFLITE_MICRO", "modelBytes": 1032, "tensorArenaBytes": 4096,
                 "tensorArenaUsedBytes": 1900, "failedInvocations": 0}
        self.assertEqual(benchmark_metrics(micro)["latency_us_from_cycles_mean"], 1)
        with self.assertRaisesRegex(ValueError, "invocaciones fallidas"):
            benchmark_metrics({**micro, "failedInvocations": 1})
        with self.assertRaisesRegex(ValueError, "Memoria de TFLite Micro"):
            benchmark_metrics({**micro, "tensorArenaUsedBytes": 4097})

    def test_stream_check_skips_broken_run_and_collects_six_consecutive_rows(self):
        def serial_row(seq, **extra):
            return json.dumps({"schemaVersion": 1, "stationId": "QA", "sessionId": "test", "sequence": seq,
                               "temperature": 23, "humidity": 63, "pressure": 736, **extra}).encode()

        class FixturePort:
            def __init__(self, lines):
                self.lines = iter(lines)

            def readline(self, _):
                return next(self.lines)

        rows = [serial_row(1), serial_row(2, pressure=None)] + [serial_row(i) for i in range(3, 8)]
        rows.append(serial_row(8, classification={"state": "OK", "source": "ESP32", "modelVersion": "qa-only",
                                                 "modelStatus": "PRELIMINARY", "label": "QA", "score": 0.7, "inferenceUs": 1}))
        result = verify_stream(FixturePort(rows), "qa-only")
        self.assertEqual([row["sequence"] for row in result["samples"]], list(range(3, 9)))
        classification = json.loads(rows[-1])["classification"]
        classified = [serial_row(i, classification=classification) for i in range(9, 14)]
        strict = verify_stream(FixturePort(rows + classified), "qa-only", consecutive_inferences=6)
        self.assertEqual([row["sequence"] for row in strict["samples"]], list(range(8, 14)))

    def test_exposure_labels_clip_initial_stabilization_and_keep_the_whole_session_in_the_split(self):
        audit = {"sessions": [{"letter": "F", "session": "SESSION", "partition": "Prueba",
                               "start": "2026-11-24T18:20:19.750-05:00", "end": "2026-11-24T18:57:42-05:00"}]}
        confirmation = {"cutoffs": ["2026-11-24T10:01:00-05:00", "2026-11-24T17:00:00-05:00"],
                        "sessions": {"F": {"observer": "QA", "evidence": "qa-notes",
                                           "intervals": [["outdoor", "2026-11-24T18:30:00-05:00", "2026-11-24T18:38:00-05:00"],
                                                         ["greenhouse", "2026-11-24T18:48:00-05:00", "2026-11-24T18:56:00-05:00"]]}}}
        labels, info = create_labels(audit, confirmation, [])
        self.assertEqual(labels[0]["start"], "2026-11-24T23:30:19.750000+00:00")
        self.assertEqual(labels[1]["start"], "2026-11-24T23:48:00+00:00")
        self.assertEqual(info[0]["split"], "test")
        confirmation["cutoffs"][1] = "2026-11-24T18:00:00-05:00"
        with self.assertRaisesRegex(ValueError, "sesión completa"):
            create_labels(audit, confirmation, [])

    def test_label_csv_format_can_be_audited_before_capture(self):
        header = b"session,start,end,label,event,observer,evidence\n"
        self.assertEqual(annotations(header), {})
        for content in (b"session,start\n", header + b"boot,2026-11-24T07:00:00-05:00\n"):
            with self.assertRaises(ValueError):
                annotations(content)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import timedelta

from scripts.tinyml_dataset import LABELS, PARTITIONS, annotations, quantize, train, utc, windows


class TinyMLDatasetTest(unittest.TestCase):
    def test_buffered_receipts_do_not_form_sensor_windows(self):
        start = utc("2026-11-23T19:00:00-05:00")
        rows = [{"id": f"qa-{i}", "sessionId": "QA", "sequence": i + 1,
                 "acquiredAt": (start + timedelta(seconds=offset)).isoformat(),
                 "temperature": 20, "humidity": 80, "pressure": 736, "quality": "VALID"}
                for i, offset in enumerate((0, 80, 80.1, 80.2, 80.3, 80.4, 80.5, 85, 90, 95, 100, 105, 110))]
        period = {"QA": [(start, start + timedelta(minutes=5), {"label": "rain", "event": "test"})]}
        result = windows(rows, period, start + timedelta(days=1), start + timedelta(days=2))
        self.assertEqual([w["ids"] for w in result["train"]], [[f"qa-{i}" for i in range(7, 13)]])

    def test_split_respects_session_event_labels_and_missing_rows(self):
        start = utc("2026-11-19T12:00:00Z")
        cutoffs = [start + timedelta(days=day) for day in (1, 2)]
        rows = []
        lines = ["session,start,end,label,event,observer,evidence"]
        for session, day in [("one", 0), ("embargo", 1), ("two", 1), ("three", 2)]:
            first = start + timedelta(days=day, minutes=0 if session == "embargo" else 31)
            for index in range(15):
                sequence = index + 1
                rows.append({"id": f"{session}-{sequence}", "sessionId": session, "sequence": sequence,
                             "acquiredAt": (first + timedelta(seconds=5 * index)).isoformat(),
                             "temperature": 22.50, "humidity": 79.50, "pressure": 735.00 - 0.03 * index,
                             "quality": "MISSING" if index == 7 else "VALID"})
            lines.append(f"{session},{first.isoformat()},{(first + timedelta(minutes=10)).isoformat()},rain,{session},QA,fixture")
        content = "\n".join(lines).encode()
        split = windows(rows, annotations(content), *cutoffs)
        self.assertEqual([len(split[s]) for s in PARTITIONS], [2, 2, 2])
        self.assertEqual([w["ids"][0] for w in split["train"]], ["one-1", "one-9"])
        self.assertEqual(tuple(map(quantize, split["train"][0]["features"])), (3, 30, -3))
        shared_event = content.replace(b",rain,two,", b",rain,one,")
        with self.assertRaisesRegex(ValueError, "más de una partición"):
            windows(rows, annotations(shared_event), *cutoffs)

    def test_training_stops_when_windows_come_from_the_same_event(self):
        split = {phase: [{"event": f"{phase}-{label}", "label": label, "features": (1, 2, 3)}
                         for label in LABELS for _ in range(20)] for phase in PARTITIONS}
        with self.assertRaisesRegex(ValueError, "2 eventos"):
            train(split)

    def test_float_and_int8_metrics_and_vectors_use_frozen_train_centroids(self):
        split = {phase: [{"event": f"{phase}-{label}-{n % 2}", "label": label,
                          "features": (0, [-10.2, 20.2][i], 0), "ids": [f"qa-{n}"]}
                         for i, label in enumerate(LABELS) for n in range(10)] for phase in PARTITIONS}
        _, weights, _, _, scores, vectors = train(split)
        self.assertEqual(weights, [(0, -10, 0), (0, 20, 0)])
        self.assertEqual(scores["test"]["int8"]["confusion"], [[10, 0], [0, 10]])
        self.assertEqual(scores["test"]["majority"]["accuracy"], 0.5)
        self.assertEqual([v["expected_index"] for v in vectors], [0] * 10 + [1] * 10)


if __name__ == "__main__":
    unittest.main()

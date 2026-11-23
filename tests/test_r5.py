"""R5 tests use an actual saved CPC issue and isolated, temporary SQLite files."""
from contextlib import closing, nullcontext
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scraper"))
from agroclima import AccessError, ROBOTS, access_delay, capture, download, fetch, watch
from noaa import URL, parse
from store import connect, export_bundle, import_bundle

HTML = ROOT / "tests/fixtures/noaa-enso-es-2026-11-12.html"
DIGEST = "56ca036e321bf1e84609f0f48d208205aa4c7f39e1ae6d24f86b681f0e7a6323"


def response(content, code=200, media="text/html", **headers):
    value = Mock(status_code=code, headers={"Content-Type": media, **headers})
    value.iter_content.return_value = [content]
    return nullcontext(value)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.raw = HTML.read_bytes()

    def test_published_issue_from_real_html(self):
        self.assertEqual(sha256(self.raw).hexdigest(), DIGEST)
        record = parse(self.raw)
        self.assertEqual(record.published, "2026-11-12")
        self.assertEqual(record.status, "Advertencia de El Niño")
        self.assertIn("continúa fortaleciéndose", record.summary)
        self.assertIn("DISCUSIÓN DIAGNÓSTICA", record.title)
        self.assertNotIn("Fig.", record.summary)
        self.assertEqual(record.url, URL)
        with self.assertRaisesRegex(ValueError, "URL de la captura"):
            parse(self.raw.replace(URL.encode(), b"https://example.org/otra-pagina", 1))

    def test_reopen_deduplicate_revisions_and_sensor_isolation(self):
        sensor = self.folder / "agroedge.sqlite"
        sensor.write_bytes(b"sensor sentinel")
        with connect(self.folder) as db:
            self.assertEqual(capture(db, HTML)["resultado"], "NUEVA")
        with connect(self.folder) as db:
            self.assertEqual(capture(db, HTML)["resultado"], "DUPLICADA")
            self.assertEqual(db.execute("SELECT count(*) FROM editions").fetchone()[0], 1)
            changed = self.folder / "correccion-de-prueba.html"
            changed.write_bytes(self.raw.replace(b"79%", b"XX%"))
            self.assertEqual(capture(db, changed)["resultado"], "NUEVA")
            self.assertEqual(db.execute("SELECT count(*) FROM editions").fetchone()[0], 2)
        self.assertEqual(sensor.read_bytes(), b"sensor sentinel")

    def test_failed_layout_does_not_replace_valid_issue(self):
        with connect(self.folder) as db:
            capture(db, HTML)
            invalid = self.folder / "error.html"
            invalid.write_bytes(self.raw.replace(b"Sinopsis:", b"Otro:"))
            with self.assertRaisesRegex(ValueError, "sinopsis"):
                capture(db, invalid)
            self.assertEqual(db.execute("SELECT raw_sha FROM editions").fetchone()[0], DIGEST)
            self.assertEqual(db.execute("SELECT outcome FROM runs ORDER BY id DESC LIMIT 1").fetchone()[0], "ERROR")

    def test_policy_two_days_and_same_day_suppression(self):
        start = datetime(2026,11,21,12,17,tzinfo=timezone.utc)
        session = Mock()
        robots = b"User-agent: *\nAllow: /\nCrawl-delay: 1"
        session.get.side_effect = [response(robots), response(self.raw), response(robots), response(self.raw)]
        sleeper = Mock()
        loader = lambda: download(session, sleeper)
        outcomes = []
        for elapsed in (timedelta(), timedelta(seconds=1), timedelta(days=1)):
            with connect(self.folder) as db:
                outcomes.append(fetch(db, loader, lambda: start+elapsed)["resultado"])
        self.assertEqual(outcomes, ["NUEVA", "EN_ESPERA", "DUPLICADA"])
        self.assertEqual([call.args[0] for call in session.get.call_args_list], [ROBOTS,URL,ROBOTS,URL])
        self.assertEqual(sleeper.call_count, 2)
        self.assertTrue(all(not c.kwargs["allow_redirects"] for c in session.get.call_args_list))

    def test_watch_executes_two_cycles_with_a_controlled_clock(self):
        instant = [datetime(2026,11,21,12,17,tzinfo=timezone.utc)]
        waits = []
        def advance(seconds):
            waits.append(seconds)
            instant[0] += timedelta(seconds=seconds)
        events = []
        with connect(self.folder) as db:
            watch(db, 2, lambda:self.raw, lambda:instant[0], advance, events.append)
            self.assertEqual(db.execute("SELECT count(*) FROM editions").fetchone()[0],1)
        self.assertEqual([json.loads(s)["resultado"] for s in events],["NUEVA","DUPLICADA"])
        self.assertEqual(waits,[23*3600])

    def test_access_errors_and_retry_after(self):
        for denied in (response(b"User-agent: *\nDisallow: /"),response(b"",403),
                       response(b"",503), response(b"",302)):
            session = Mock()
            session.get.return_value = denied
            with self.assertRaises(AccessError):
                download(session)
            self.assertEqual(session.get.call_count,1)
        for result in (response(b"{}",media="application/json"), response(b"",429)):
            session = Mock()
            session.get.side_effect = [response(b"",404), result]
            with self.assertRaises(ValueError):
                download(session)
        with connect(self.folder) as db:
            with self.assertRaises(AccessError):
                fetch(db, Mock(side_effect=AccessError("429","2030-01-03T00:00:00Z")),
                      lambda:datetime(2026,11,21,tzinfo=timezone.utc))
            self.assertEqual(db.execute("SELECT next_at FROM policy").fetchone()[0], "2030-01-03T00:00:00Z")
            self.assertEqual(db.execute("SELECT outcome FROM runs").fetchone()[0], "ERROR")

    def test_robots_wildcards_specificity_and_slowest_rate(self):
        with self.assertRaises(AccessError):
            access_delay("User-agent: *\nDisallow: /*advisory/*.shtml$")
        policy = ("User-agent: *\nDisallow: /\nUser-agent: AgroEdgeR5\nDisallow: /products/\n"
                  "Allow: /products/analysis_monitoring/\nCrawl-delay: 0.5\nRequest-rate: 2/4")
        self.assertEqual(access_delay(policy),2)

    def test_sync_integrity_atomicity_and_replay(self):
        bundle = self.folder / "r5.json"
        with connect(self.folder) as db:
            capture(db, HTML)
            export_bundle(db, bundle)
        copy = self.folder / "local"
        with connect(copy) as db:
            self.assertEqual(import_bundle(db, bundle)["nuevas"], 1)
            self.assertEqual(import_bundle(db, bundle)["nuevas"], 0)
            row = db.execute("SELECT raw_html,live_seen FROM editions").fetchone()
            self.assertEqual(row["raw_html"], self.raw)
            self.assertIsNone(row["live_seen"])
        payload=json.loads(bundle.read_bytes())
        payload["editions"].append(dict(payload["editions"][0], raw_sha="alterado"))
        bundle.write_text(json.dumps(payload))
        with connect(self.folder/"fresh") as db:
            with self.assertRaisesRegex(ValueError, "huella"):
                import_bundle(db, bundle)
            self.assertEqual(db.execute("SELECT count(*) FROM editions").fetchone()[0],0)

    def test_protect_existing_unrelated_database(self):
        path = self.folder / "agroclima.sqlite"
        with closing(sqlite3.connect(path)) as other:
            other.execute("CREATE TABLE readings(id INTEGER)")
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError,"otra base"):
            with connect(self.folder):
                pass
        self.assertEqual(before,path.read_bytes())


if __name__ == "__main__":
    unittest.main()

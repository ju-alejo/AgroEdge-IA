from contextlib import closing, redirect_stderr
from datetime import datetime, timedelta, timezone
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from scripts.ejecutar_toca_r5 import run

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scraper"))
import toca_forecast as toca
from toca_policy import authorize_once, reserve, restrict


def response(status, raw, **headers):
    result = Mock(status_code=status, headers=headers)
    result.__enter__ = Mock(return_value=result)
    result.__exit__ = Mock(return_value=False)
    result.iter_content.return_value = [raw]
    return result


class TocaAutomationTest(unittest.TestCase):
    def test_launcher_preserves_process_code_output_and_errors(self):
        with TemporaryDirectory() as temp:
            folder = Path(temp)
            command = [sys.executable, "-c", "import sys; print('salida'); print('error', file=sys.stderr); sys.exit(1)"]
            self.assertEqual(run(folder, command, folder), 1)
            attempt, = (folder / "pronostico-toca-ejecuciones").iterdir()
            self.assertEqual((attempt / "stdout.log").read_text().strip(), "salida")
            self.assertEqual((attempt / "stderr.log").read_text().strip(), "error")
            report = json.loads((attempt / "ejecucion.json").read_text())
            self.assertEqual(report["codigo_salida"], 1)
            self.assertEqual(report["comando"], command)
            self.assertIn("fin_utc", report)

    def test_transition_to_morning_does_not_bypass_existing_reservation(self):
        check = datetime(2026, 11, 25, 14, tzinfo=timezone.utc)
        next_at = "2026-11-26T00:45:01Z"
        with TemporaryDirectory() as temp, closing(toca.connect(Path(temp))) as db, \
                patch("requests.Session.get") as request, patch.dict("os.environ", {"AGROEDGE_TOCA_TRACE": "1"}), \
                redirect_stderr(io.StringIO()) as stderr:
            with db:
                db.execute("INSERT INTO policy VALUES(1,?)", (next_at,))
            self.assertEqual(toca.fetch(db, check), {"resultado": "EN_ESPERA", "proxima_consulta_utc": next_at})
            request.assert_not_called()
            self.assertEqual(db.execute("SELECT next_at FROM policy").fetchone()[0], next_at)
            self.assertEqual(json.loads(stderr.getvalue())["evento"], "limite_vigente")

    def test_http_failure_identifies_stage_and_preserves_retry_after(self):
        check = datetime(2026, 11, 26, 14, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp, closing(toca.connect(Path(temp))) as db, \
                patch("requests.Session.get", side_effect=[response(200, b"User-agent: *\nAllow: /"),
                     response(429, b"", **{"Retry-After": "Fri, 27 Nov 2026 18:00:00 GMT"})]) as request, \
                patch.dict("os.environ", {"AGROEDGE_TOCA_TRACE": "1"}), redirect_stderr(io.StringIO()) as stderr:
            with self.assertRaisesRegex(toca.AccessError, "HTTP 429"):
                toca.fetch(db, check)
            self.assertEqual(request.call_count, 2)
            events = [json.loads(line) for line in stderr.getvalue().splitlines()]
            self.assertEqual([event["estado"] for event in events if event["evento"] == "respuesta_http"], [200, 429])
            self.assertEqual(events[-2]["url"], toca.URL)
            self.assertEqual(db.execute("SELECT next_at FROM policy").fetchone()[0], "2026-11-26T20:00:00Z")
            self.assertEqual(db.execute("SELECT until_utc FROM external_policy").fetchone()[0], "2026-11-27T18:00:00Z")
            self.assertEqual(toca.fetch(db, check + timedelta(days=1))["resultado"], "BLOQUEO_EXTERNO")
            self.assertEqual(request.call_count, 2)
            self.assertEqual(db.execute("SELECT count(*) FROM snapshots").fetchone()[0], 0)

    def test_authorization_is_consumed_once_and_reserves_six_hours(self):
        start = datetime(2026, 11, 25, 2, 20, tzinfo=timezone.utc)
        legacy = "2026-11-26T00:45:01Z"
        with TemporaryDirectory() as temp, closing(toca.connect(Path(temp))) as db:
            with db:
                db.execute("INSERT INTO policy VALUES(1,?)", (legacy,))
            authorize_once(db, start, start + timedelta(hours=2), legacy, "Prueba académica autorizada")
            self.assertEqual(reserve(db, start), (None, legacy))
            used = db.execute("SELECT previous_next_at,used_at FROM one_time_authorizations").fetchone()
            self.assertEqual(used, (legacy, "2026-11-25T02:20:00Z"))
            self.assertEqual(reserve(db, start + timedelta(hours=5))[0]["proxima_consulta_utc"], "2026-11-25T08:20:00Z")
            self.assertEqual(reserve(db, start + timedelta(hours=6)), (None, None))

    def test_external_block_precedes_even_an_existing_authorization(self):
        start = datetime(2026, 11, 25, 2, 20, tzinfo=timezone.utc)
        legacy = "2026-11-26T00:45:01Z"
        with TemporaryDirectory() as temp, closing(toca.connect(Path(temp))) as db:
            with db:
                db.execute("INSERT INTO policy VALUES(1,?)", (legacy,))
            authorize_once(db, start, start + timedelta(hours=2), legacy, "Prueba académica autorizada")
            restrict(db, "HTTP 403", None)
            self.assertEqual(reserve(db, start)[0]["resultado"], "BLOQUEO_EXTERNO")
            self.assertIsNone(db.execute("SELECT used_at FROM one_time_authorizations").fetchone()[0])
            with self.assertRaisesRegex(ValueError, "restricción externa vigente"):
                authorize_once(db, start, start + timedelta(hours=2), legacy, "Otra autorización")

    def test_robots_403_stops_before_forecast_and_blocks_unattended_retries(self):
        start = datetime(2026, 11, 25, 2, 20, tzinfo=timezone.utc)
        with TemporaryDirectory() as temp, closing(toca.connect(Path(temp))) as db, \
                patch("requests.Session.get", return_value=response(403, b"")) as request:
            with self.assertRaisesRegex(toca.AccessError, "HTTP 403"):
                toca.fetch(db, start)
            self.assertEqual(toca.fetch(db, start + timedelta(days=1))["resultado"], "BLOQUEO_EXTERNO")
            request.assert_called_once()
            self.assertEqual(request.call_args.args[0], toca.ROBOTS)

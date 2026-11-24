"""CLI for the AgroEdge R5 bulletin. Typical usage: py scraper/agroclima.py fetch"""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from fnmatch import fnmatchcase
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import time
from urllib.parse import unquote, urlsplit

from noaa import MAX_HTML, URL
from store import connect, export_bundle, import_bundle, log, now, save

DEFAULT_DIR = Path(__file__).resolve().parents[1] / "data"
UA = "AgroEdgeR5/0.2 (university agroclimate bulletin reader)"
ROBOTS = "https://www.cpc.ncep.noaa.gov/robots.txt"


class AccessError(ValueError):
    def __init__(self, message, retry_at=None):
        super().__init__(message)
        self.retry_at = retry_at


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def retry_time(value):
    if not value:
        return None
    try:
        if value.isascii() and value.isdigit():
            return iso(datetime.now(timezone.utc) + timedelta(seconds=int(value)))
        dt = parsedate_to_datetime(value)
        return iso(dt) if dt.tzinfo else None
    except (OverflowError, ValueError, TypeError):
        return None


def response_bytes(response, limit):
    result = bytearray()
    for chunk in response.iter_content(8192):
        result.extend(chunk)
        if len(result) > limit:
            raise ValueError("Respuesta HTTP demasiado grande.")
    return bytes(result)


def access_delay(text, url=URL, user_agent=UA):
    """Evaluate REP groups for the fixed, ASCII bulletin path, including * and $ patterns."""
    groups = []
    agents, rules = [], []
    for raw in text.splitlines():
        key, sep, val = raw.split("#",1)[0].partition(":")
        if not sep:
            continue
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            if rules:
                groups.append((agents,rules))
                agents, rules = [], []
            agents.append(val.lower())
        elif agents:
            rules.append((key,val))
    groups.append((agents,rules))
    product = user_agent.split("/")[0].lower()
    matching = []
    for names, directives in groups:
        named = [len(name) for name in names if name and name != "*" and name in product]
        if named:
            matching.append((max(named), directives))
        elif "*" in names:
            matching.append((0, directives))
    specificity = max((n for n,_ in matching),default=-1)
    matches = []
    delay = 0.0
    for n, rules in matching:
        if n != specificity:
            continue
        for key, val in rules:
            if key in ("allow","disallow") and val:
                path = unquote(val)
                exact = path.endswith("$")
                pattern = path[:-1] if exact else path
                glob = pattern.replace("[","[[]").replace("?","[?]")
                if fnmatchcase(urlsplit(url).path, glob if exact else glob + "*"):
                    matches.append((len(pattern.replace("*","")),key == "allow"))
            elif key == "crawl-delay":
                if not re.fullmatch(r"\d+(?:\.\d+)?",val):
                    raise AccessError("Crawl-delay no interpretable.")
                delay = max(delay,float(val))
            elif key == "request-rate":
                rate = re.fullmatch(r"([1-9]\d*)\s*/\s*([1-9]\d*)",val)
                if not rate:
                    raise AccessError("Request-rate no interpretable.")
                delay = max(delay,int(rate[2])/int(rate[1]))
    if matches and not max(matches)[1]:
        raise AccessError("robots.txt impide la consulta.")
    if delay > 60:
        raise AccessError("El ritmo de robots.txt exige revisar la programación.")
    return delay


def download(session, sleep=time.sleep, *, url=URL, robots=ROBOTS, user_agent=UA):
    def get(address):
        return session.get(address, headers={"User-Agent": user_agent, "Accept": "text/html,text/plain,application/xhtml+xml"}, timeout=(8, 20),
                           stream=True, allow_redirects=False)

    def check(response):
        if response.status_code != 200:
            raise AccessError(f"HTTP {response.status_code}. Consulta detenida.",
                              retry_time(response.headers.get("Retry-After")))

    with get(robots) as response:
        if response.status_code not in (404, 410):
            check(response)
            rules = response_bytes(response, MAX_HTML).decode("utf-8-sig")
            if "<html" in rules.lower() or "<!doctype html" in rules.lower():
                raise AccessError("La respuesta no es un archivo robots.txt válido.")
            delay = access_delay(rules, url, user_agent)
            if delay:
                sleep(delay)
    with get(url) as response:
        check(response)
        if response.headers.get("Content-Type", "").partition(";")[0].strip().lower() not in (
                "text/html", "application/xhtml+xml"):
            raise ValueError("La fuente no devolvió HTML.")
        return response_bytes(response, MAX_HTML)


def live_bytes():
    try:
        import requests
    except ImportError as e:
        raise ValueError("Instala las dependencias con py -m pip install -r scraper/requirements.txt.") from e
    try:
        with requests.Session() as session:
            return download(session)
    except requests.RequestException as e:
        raise ValueError(f"Conexión a {urlsplit(URL).hostname} fallida ({type(e).__name__}).") from e


def reserve_daily(db, start):
    stamp = iso(start)
    with db:
        db.execute("BEGIN IMMEDIATE")
        gate = db.execute("SELECT next_at FROM policy WHERE id=1").fetchone()
        if gate and stamp < gate[0]:
            return {"resultado": "EN_ESPERA", "proxima_consulta_utc": gate[0]}
        next_day = (start + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        next_time = max(start + timedelta(hours=23), next_day)
        db.execute("INSERT OR REPLACE INTO policy VALUES(1,?)", (iso(next_time),))


def fetch(db, loader=live_bytes, clock=lambda: datetime.now(timezone.utc)):
    start = clock()
    stamp = iso(start)
    if waiting := reserve_daily(db, start):
        return waiting
    try:
        raw = loader()
        with db:
            return save(db, raw, "HTTPS", stamp, stamp, stamp)
    except (ValueError, OSError) as e:
        with db:
            if isinstance(e, AccessError) and e.retry_at:
                db.execute("UPDATE policy SET next_at=max(next_at,?) WHERE id=1", (e.retry_at,))
            log(db, "HTTPS", "ERROR", str(e))
        raise


def capture(db, path):
    with Path(path).open("rb") as f:
        raw = f.read(MAX_HTML + 1)
    stamp = now()
    try:
        with db:
            return save(db, raw, "ARCHIVO_HTML", stamp, stamp)
    except ValueError as e:
        with db:
            log(db, "ARCHIVO_HTML", "ERROR", str(e))
        raise


def watch(db, cycles=None, loader=live_bytes, clock=lambda: datetime.now(timezone.utc),
          sleep=time.sleep, emit=print):
    """Wait on the persisted policy between attempts without holding a database transaction."""
    count = 0
    while cycles is None or count < cycles:
        try:
            emit(json.dumps(fetch(db, loader, clock), ensure_ascii=True))
        except (ValueError, OSError) as e:
            emit(f"R5: {e}")
        count += 1
        if cycles is None or count < cycles:
            due = datetime.fromisoformat(db.execute("SELECT next_at FROM policy").fetchone()[0].replace("Z","+00:00"))
            sleep(max(1, min(86400, (due - clock()).total_seconds())))


def run(argv=None):
    parser = argparse.ArgumentParser(description="Boletín ENSO de NOAA para AgroEdge IA.")
    parser.add_argument("--dir", default=os.environ.get("AGROEDGE_R5_DIR") or DEFAULT_DIR,
                        help="Carpeta de la base independiente agroclima.sqlite")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("fetch", help="Consultar el HTML del CPC respetando el intervalo y robots.txt")
    sub.add_parser("watch", help="Mantener la consulta periódica en primer plano hasta Ctrl+C")
    sub.add_parser("status", help="Consultar últimas ejecuciones y número de versiones")
    for cmd in ("capture", "export", "sync"):
        sub.add_parser(cmd).add_argument("file")
    args = parser.parse_args(argv)
    with connect(args.dir) as db:
        if args.action == "fetch":
            value = fetch(db)
        elif args.action == "watch":
            watch(db)
            return
        elif args.action == "capture":
            value = capture(db, args.file)
        elif args.action == "export":
            value = {"versiones_exportadas": export_bundle(db, args.file)}
        elif args.action == "sync":
            value = import_bundle(db, args.file)
        else:
            value = {"versiones": db.execute("SELECT count(*) FROM editions").fetchone()[0],
                     "ejecuciones": [dict(r) for r in db.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 10")]}
    print(json.dumps(value, ensure_ascii=True))


if __name__ == "__main__":
    try:
        run()
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        print(f"R5: {error}", file=sys.stderr)
        sys.exit(1)

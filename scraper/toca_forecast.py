"""Collect the attributed public hourly forecast table for Toca, Boyacá."""

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from bs4 import BeautifulSoup
import requests

from agroclima import AccessError, DEFAULT_DIR, download, iso, reserve_daily


URL = "https://eltiempoen.net/colombia/el-tiempo-en-toca"
ROBOTS = "https://eltiempoen.net/robots.txt"
USER_AGENT = "AgroEdgeIA/1.0 (local non-commercial university forecast reader)"
APP_ID = 0x41474643
BOGOTA = timezone(timedelta(hours=-5))
WEEKDAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
FIELDS = {"Temperatura °C": ("temperatureC", -60, 70), "Lluvia mm": ("precipitationMm", 0, 1000),
          "Probabilidad %": ("probabilityPct", 0, 100), "Viento km/h": ("windKmh", 0, 400),
          "Humedad %": ("humidityPct", 0, 100)}


def trace(event, **details):
    if os.environ.get("AGROEDGE_TOCA_TRACE") == "1":
        print(json.dumps({"utc": iso(datetime.now(timezone.utc)), "evento": event, **details}), file=sys.stderr, flush=True)


class ForecastSession(requests.Session):
    def get(self, url, **kwargs):
        trace("intento_https", url=url)
        response = super().get(url, **kwargs)
        trace("respuesta_http", url=url, estado=response.status_code, retry_after=response.headers.get("Retry-After"))
        return response


def number(cell, minimum, maximum):
    value = cell.get_text(" ", strip=True).replace(",", ".")
    if value in ("", "—", "-"):
        return None
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise ValueError(f"Valor no numérico en el pronóstico: {value[:20]}.")
    result = float(value)
    if not minimum <= result <= maximum:
        raise ValueError("Valor fuera del rango del campo meteorológico.")
    return result


def parse_forecast(raw, retrieved):
    soup = BeautifulSoup(raw, "html.parser")
    canonical, title = soup.select_one('link[rel="canonical"]'), soup.find("h1")
    if not canonical or canonical.get("href") != URL or not title or title.get_text(" ", strip=True) != "El tiempo en Toca":
        raise ValueError("La página no identifica el pronóstico municipal esperado.")
    attribution = soup.find("footer")
    if not attribution or "open-meteo" not in attribution.get_text(" ", strip=True).lower():
        raise ValueError("La fuente ya no expone la atribución verificada a Open-Meteo.")
    tables = soup.select("table.tabla--calor")
    if len(tables) != 2:
        raise ValueError("Se esperaban las tablas horarias de hoy y mañana.")
    hours = []
    for offset, table in enumerate(tables):
        day = retrieved.astimezone(BOGOTA).date() + timedelta(days=offset)
        header = [cell.get_text(" ", strip=True) for cell in table.select("thead th")]
        if header != [f"{WEEKDAYS[day.weekday()]} {day.day}", *(f"{h:02}" for h in range(24))]:
            raise ValueError("Día u horas de la tabla incompatibles con la captura en Bogotá.")
        rows = {}
        for row in table.select("tbody tr"):
            label = row.find("th").get_text(" ", strip=True)
            if label in rows:
                raise ValueError(f"Fila duplicada: {label}.")
            rows[label] = row.find_all("td", recursive=False)
        if any(len(rows.get(label, ())) != 24 for label in (*FIELDS, "Cielo")):
            raise ValueError("Faltan variables u horas en la tabla publicada.")
        for hour in range(24):
            sky = rows["Cielo"][hour].select_one(".f-cielo[title]")
            description = sky.get("title", "").strip() if sky else ""
            instant = datetime(day.year, day.month, day.day, hour, tzinfo=BOGOTA)
            hours.append({"validAt": iso(instant), "sky": description[:100] or None,
                          **{name: number(rows[label][hour], lo, hi) for label, (name, lo, hi) in FIELDS.items()}})
    return hours


def connect(directory):
    directory.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(directory / "pronostico-toca.sqlite", timeout=5)
    try:
        owner = database.execute("PRAGMA application_id").fetchone()[0]
        if owner != APP_ID and (owner != 0 or database.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()):
            raise ValueError("La base pertenece a otra aplicación.")
        database.executescript(f"PRAGMA application_id={APP_ID}; PRAGMA journal_mode=WAL; "
                               "CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY,next_at TEXT NOT NULL); "
                               "CREATE TABLE IF NOT EXISTS snapshots(revision TEXT PRIMARY KEY, fetched_at TEXT NOT NULL, "
                               "method TEXT NOT NULL, raw_sha TEXT NOT NULL, payload TEXT NOT NULL);")
        return database
    except BaseException:
        database.close()
        raise


def save(database, raw, retrieved, method):
    hours = parse_forecast(raw, retrieved)
    payload = json.dumps(hours, ensure_ascii=False, separators=(",", ":"))
    revision = sha256(payload.encode()).hexdigest()
    with database:
        cursor = database.execute("INSERT OR IGNORE INTO snapshots VALUES (?,?,?,?,?)",
                                  (revision, iso(retrieved), method, sha256(raw).hexdigest(), payload))
    return {"resultado": "NUEVA" if cursor.rowcount else "REPETIDA", "revision": revision, "horas": len(hours)}


def fetch(database, retrieved):
    if waiting := reserve_daily(database, retrieved):
        trace("limite_vigente", proxima_consulta_utc=waiting["proxima_consulta_utc"])
        return waiting
    trace("reserva_confirmada", inicio_consulta_utc=iso(retrieved))
    with ForecastSession() as session:
        try:
            raw = download(session, url=URL, robots=ROBOTS, user_agent=USER_AGENT)
            trace("html_recibido", bytes=len(raw), sha256=sha256(raw).hexdigest())
            return save(database, raw, retrieved, "HTTPS")
        except AccessError as error:
            if error.retry_at:
                with database:
                    database.execute("UPDATE policy SET next_at=max(next_at,?) WHERE id=1", (error.retry_at,))
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=Path(os.environ.get("AGROEDGE_R5_DIR") or DEFAULT_DIR))
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("fetch")
    capture = commands.add_parser("capture")
    capture.add_argument("file", type=Path)
    capture.add_argument("--at", required=True, type=datetime.fromisoformat)
    args = parser.parse_args()
    with closing(connect(args.dir)) as database:
        if args.action == "fetch":
            result = fetch(database, datetime.now(timezone.utc))
        else:
            if args.at.tzinfo is None:
                parser.error("--at requiere una zona horaria explícita.")
            result = save(database, args.file.read_bytes(), args.at, "ARCHIVO_HTML")
    print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, AttributeError, sqlite3.Error, requests.RequestException) as error:
        trace("error", tipo=type(error).__name__)
        print(f"Pronóstico Toca: {error}", file=sys.stderr)
        sys.exit(1)

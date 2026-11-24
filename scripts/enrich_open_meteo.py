"""Archive Open-Meteo products beside a campaign and link completed hours by reading ID."""

import argparse
from collections import Counter
from contextlib import closing
import csv
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

import requests


SECONDS_PER_HOUR = 3600
BOGOTA = timezone(timedelta(hours=-5))
UNITS = {"temperature_2m": "°C", "relative_humidity_2m": "%", "surface_pressure": "hPa",
         "precipitation": "mm", "wind_speed_10m": "km/h", "cloud_cover": "%", "precipitation_probability": "%"}
PRODUCTS = {
    "historical_forecast": ("https://historical-forecast-api.open-meteo.com/v1/forecast", "best_match", "", tuple(UNITS)),
    "previous_run_24h": ("https://previous-runs-api.open-meteo.com/v1/forecast", "gfs_seamless", "_previous_day1", tuple(UNITS)[:-1]),
    "era5_reanalysis": ("https://archive-api.open-meteo.com/v1/archive", "era5", "", tuple(UNITS)[:-1]),
}


def receipt_time(row):
    stamp = datetime.fromisoformat(row["received_utc"])
    if stamp.tzinfo is None:
        raise ValueError("Una hora de recepción carece de zona horaria.")
    return stamp


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def parse_hours(data, suffix, variables):
    hourly, units = data["hourly"], data["hourly_units"]
    epochs = hourly["time"]
    if (not epochs or any(type(t) is not int or t % SECONDS_PER_HOUR for t in epochs)
            or any(b - a != SECONDS_PER_HOUR for a, b in zip(epochs, epochs[1:]))):
        raise ValueError("Horas vacías, duplicadas o no consecutivas.")
    for key in variables:
        field = key + suffix
        if units[field] != UNITS[key] or len(hourly[field]) != len(epochs):
            raise ValueError(f"Serie o unidad incompatible: {field}.")
        if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v)) for v in hourly[field]):
            raise ValueError(f"Valores incompatibles: {field}.")
    return {epoch: {key: hourly[key + suffix][i] for key in variables} for i, epoch in enumerate(epochs)}


def align(row, product, hours):
    # An hourly precipitation value covers the hour ending at its valid timestamp.
    eligible = row["receipt_timing_uncertain"] == "0"
    end = int(receipt_time(row).timestamp()) // SECONDS_PER_HOUR * SECONDS_PER_HOUR if eligible else None
    values = hours.get(end, {})
    available = any(v is not None for v in values.values())
    status = "receipt_uncertain" if not eligible else "matched" if available else "unavailable"
    return {"reading_id": row["reading_id"], "received_utc": row["received_utc"], "product": product,
            "valid_hour_end_utc": iso(end) if end is not None else None,
            "nominal_forecast_cutoff_utc": iso(end - 24 * SECONDS_PER_HOUR) if end is not None and product == "previous_run_24h" else None,
            "join_status": status, "use": "retrospective_context_only", **{key: values.get(key) for key in UNITS}}


def collect(session, product, params, output, raw_dir):
    url, model, suffix, variables = PRODUCTS[product]
    request = requests.Request("GET", url, params={**params, "models": model,
                                                   "hourly": ",".join(key + suffix for key in variables)}).prepare()
    metadata = {"product": product, "url": request.url, "model": model, "source": "Open-Meteo",
                "license": "CC BY 4.0", "use": "retrospective_context_only"}
    raw_path = output / f"{product}.json"
    try:
        if raw_dir is None:
            with session.get(request.url, timeout=(5, 15), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise ValueError(f"HTTP {response.status_code}")
                raw = response.content
            metadata["retrieved_at"] = datetime.now(timezone.utc).isoformat()
        else:
            raw = (raw_dir / raw_path.name).read_bytes()
            metadata["retrieved_at"] = None
        raw_path.write_bytes(raw)
        metadata["sha256"] = sha256(raw).hexdigest()
        data = json.loads(raw)
        for key in ("latitude", "longitude", "elevation", "timezone", "utc_offset_seconds"):
            metadata[key] = data[key]
        hours = parse_hours(data, suffix, variables)
    except (requests.RequestException, OSError, KeyError, TypeError, ValueError) as error:
        return metadata | {"status": "unavailable", "detail": str(error)[:250]}, {}
    coverage = {key: sum(values[key] is not None for values in hours.values()) for key in variables}
    status = "available" if all(n == len(hours) for n in coverage.values()) else "partial" if any(coverage.values()) else "no_values"
    return metadata | {"status": status, "hours": len(hours), "non_null": coverage}, hours


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--raw-dir", type=Path, help="Reproducir desde JSON archivado sin consultar la red")
    args = parser.parse_args()
    csv_path = args.dataset / "mediciones.csv"
    with csv_path.open(encoding="utf-8-sig", newline="") as file:
        readings = list(csv.DictReader(file))
    stamps = [receipt_time(row).astimezone(BOGOTA) for row in readings]
    params = {"latitude": 5.56112, "longitude": -73.18294, "timezone": "America/Bogota", "timeformat": "unixtime",
              "start_date": min(stamps).date().isoformat(), "end_date": max(stamps).date().isoformat()}
    with TemporaryDirectory(dir=args.output.parent) as temporary, requests.Session() as session:
        pending = Path(temporary) / args.output.name
        pending.mkdir()
        session.headers.update({"User-Agent": "AgroEdgeIA/1.0 (non-commercial university weather research)", "Accept": "application/json"})
        products, by_reading = [], []
        with closing(sqlite3.connect(pending / "contexto.sqlite")) as database, database:
            database.executescript("CREATE TABLE products (id TEXT PRIMARY KEY, metadata TEXT NOT NULL); "
                                   "CREATE TABLE hourly (product TEXT NOT NULL REFERENCES products(id), valid_utc TEXT NOT NULL, "
                                   "values_json TEXT NOT NULL, PRIMARY KEY(product,valid_utc)); PRAGMA foreign_keys=ON;")
            for product in PRODUCTS:
                metadata, hours = collect(session, product, params, pending, args.raw_dir)
                linked = [align(row, product, hours) for row in readings]
                metadata["joins"] = Counter(row["join_status"] for row in linked)
                products.append(metadata)
                by_reading.extend(linked)
                database.execute("INSERT INTO products VALUES (?,?)", (product, json.dumps(metadata)))
                database.executemany("INSERT INTO hourly VALUES (?,?,?)",
                                     ((product, iso(epoch), json.dumps(values)) for epoch, values in hours.items()))
        with (pending / "contexto-por-lectura.csv").open("w", encoding="utf-8-sig", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=by_reading[0].keys())
            writer.writeheader()
            writer.writerows(by_reading)
        manifest = {"schema": "agroedge.open-meteo-context.v1", "station_csv_sha256": sha256(csv_path.read_bytes()).hexdigest(),
                    "requested_point": params, "units": UNITS, "products": products}
        (pending / "resumen.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        pending.rename(args.output)
    print(json.dumps({meta["product"]: {"status": meta["status"], "joins": meta["joins"]} for meta in products}))


if __name__ == "__main__":
    main()

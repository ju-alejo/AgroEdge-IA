"""Independent R5 store. Sensor databases and existing databases of other types are rejected."""
from base64 import b64decode, b64encode
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from tempfile import NamedTemporaryFile

from noaa import MAX_HTML, parse

APP_ID = 0x41475235
SCHEMA = "agroedge.r5.v1"
LIMIT_SYNC = 32 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def timestamp(s):
    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")
    if dt.strftime("%Y-%m-%dT%H:%M:%SZ") != s:
        raise ValueError("Fecha UTC inválida.")
    return s


@contextmanager
def connect(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "agroclima.sqlite"
    if path.is_symlink() or (path.exists() and path.stat().st_nlink > 1):
        raise ValueError("La base R5 no puede ser un enlace.")
    db = sqlite3.connect(path, timeout=8)
    db.row_factory = sqlite3.Row
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            app_id = db.execute("PRAGMA application_id").fetchone()[0]
            if app_id != APP_ID:
                if app_id or db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone():
                    raise ValueError("Este archivo pertenece a otra base de datos.")
                db.execute(f"PRAGMA application_id={APP_ID}")
            db.execute("""CREATE TABLE IF NOT EXISTS editions(
                revision TEXT PRIMARY KEY, published TEXT NOT NULL, title TEXT NOT NULL,
                status TEXT NOT NULL, summary TEXT NOT NULL, source TEXT NOT NULL, url TEXT NOT NULL,
                first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, live_seen TEXT,
                raw_sha TEXT NOT NULL, raw_html BLOB NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS editions_recent ON editions(published DESC,last_seen DESC,revision)")
            db.execute("""CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, at TEXT NOT NULL,
                method TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL,
                revision TEXT, raw_sha TEXT)""")
            db.execute("CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1), next_at TEXT NOT NULL)")
        yield db
    finally:
        db.close()


def log(db, method, outcome, detail="", revision=None, digest=None):
    db.execute("INSERT INTO runs(at,method,outcome,detail,revision,raw_sha) VALUES(?,?,?,?,?,?)",
               (now(), method, outcome, detail, revision, digest))


def save(db, raw, method, first, last, live=None):
    item = parse(raw)
    digest = sha256(raw).hexdigest()
    args = (item.revision, item.published, item.title, item.status, item.summary, item.source,
            item.url, first, last, live, digest, raw)
    added = db.execute("INSERT OR IGNORE INTO editions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", args).rowcount
    if not added:
        db.execute("""UPDATE editions SET first_seen=min(first_seen,?), last_seen=max(last_seen,?),
                   live_seen=CASE WHEN live_seen IS NULL OR live_seen < ? THEN coalesce(?,live_seen)
                   ELSE live_seen END WHERE revision=?""", (first, last, live, live, item.revision))
    outcome = "NUEVA" if added else "DUPLICADA"
    log(db, method, outcome, item.published, item.revision, digest)
    return {"resultado": outcome, "publicacion": item.published, "revision": item.revision, "sha256_html": digest}


def export_bundle(db, destination):
    path = Path(destination)
    if path.suffix.lower() != ".json":
        raise ValueError("El destino de sincronización debe terminar en .json.")
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in db.execute("SELECT * FROM editions ORDER BY published,revision"):
        rows.append({k: r[k] for k in ("first_seen","last_seen","live_seen","revision","raw_sha")} |
                    {"html_b64": b64encode(r["raw_html"]).decode("ascii")})
    data = json.dumps({"schema": SCHEMA, "editions": rows}, ensure_ascii=False, separators=(",", ":")).encode()
    if len(data) > LIMIT_SYNC:
        raise ValueError("El paquete supera el límite de sincronización.")
    with NamedTemporaryFile(dir=path.parent, delete=False) as f:
        tmp = Path(f.name)
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)
    return len(rows)


def import_bundle(db, path):
    with Path(path).open("rb") as f:
        data = f.read(LIMIT_SYNC + 1)
    if len(data) > LIMIT_SYNC:
        raise ValueError("Paquete JSON demasiado grande.")
    bundle = json.loads(data)
    if not isinstance(bundle, dict) or bundle.get("schema") != SCHEMA or not isinstance(bundle.get("editions"), list):
        raise ValueError("Formato de sincronización desconocido.")
    new = 0
    with db:
        for entry in bundle["editions"]:
            if not isinstance(entry, dict) or len(entry["html_b64"]) > MAX_HTML * 2:
                raise ValueError("Entrada de sincronización inválida.")
            raw = b64decode(entry["html_b64"], validate=True)
            first, last = timestamp(entry["first_seen"]), timestamp(entry["last_seen"])
            live = entry["live_seen"]
            if first > last or (live is not None and not first <= timestamp(live) <= last):
                raise ValueError("Intervalo de captura inválido.")
            if sha256(raw).hexdigest() != entry["raw_sha"] or parse(raw).revision != entry["revision"]:
                raise ValueError("La huella del paquete no coincide con el HTML.")
            new += save(db, raw, "SYNC", first, last, live)["resultado"] == "NUEVA"
        log(db, "SYNC", "IMPORTADA", f"{new} nuevas de {len(bundle['editions'])}")
    return {"nuevas": new, "total_paquete": len(bundle["editions"])}

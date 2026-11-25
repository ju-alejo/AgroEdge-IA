"""Keep Eltiempoen.net's access restrictions separate from AgroEdge's interval."""

from datetime import timedelta

from agroclima import iso


INTERVAL = timedelta(hours=6)
SCHEMA = """
CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY,next_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS external_policy(id INTEGER PRIMARY KEY,reason TEXT NOT NULL,until_utc TEXT);
CREATE TABLE IF NOT EXISTS one_time_authorizations(
    previous_next_at TEXT PRIMARY KEY, authorized_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    reason TEXT NOT NULL, used_at TEXT
);
"""


def external_block(db, stamp):
    row = db.execute("SELECT reason,until_utc FROM external_policy WHERE id=1").fetchone()
    if row and (row[1] is None or stamp < row[1]):
        return {"resultado": "BLOQUEO_EXTERNO", "motivo": row[0], "proxima_consulta_utc": row[1]}


def restrict(db, reason, until):
    with db:
        db.execute("INSERT INTO external_policy VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET "
                   "reason=excluded.reason, until_utc=excluded.until_utc WHERE external_policy.until_utc IS NOT NULL "
                   "AND (excluded.until_utc IS NULL OR excluded.until_utc > external_policy.until_utc)", (reason, until))


def authorize_once(db, now, expires, expected_gate, reason):
    stamp, deadline = iso(now), iso(expires)
    if deadline <= stamp or not reason.strip():
        raise ValueError("La autorización requiere una justificación y un vencimiento futuro.")
    with db:
        db.execute("BEGIN IMMEDIATE")
        if external_block(db, stamp):
            raise ValueError("Existe una restricción externa vigente.")
        if db.execute("SELECT next_at FROM policy WHERE id=1").fetchone() != (expected_gate,) or stamp >= expected_gate:
            raise ValueError("La reserva interna vigente difiere de la que se autorizó adelantar.")
        db.execute("INSERT INTO one_time_authorizations VALUES(?,?,?,?,NULL)", (expected_gate, stamp, deadline, reason))
    return {"resultado": "AUTORIZADA_UNA_VEZ", "reserva_anterior_utc": expected_gate, "vence_utc": deadline}


def reserve(db, now):
    stamp = iso(now)
    with db:
        db.execute("BEGIN IMMEDIATE")
        if restriction := external_block(db, stamp):
            return restriction, None
        gate = db.execute("SELECT next_at FROM policy WHERE id=1").fetchone()
        authorization = None
        if gate and stamp < gate[0]:
            used = db.execute("UPDATE one_time_authorizations SET used_at=? WHERE previous_next_at=? "
                              "AND used_at IS NULL AND authorized_at<=? AND expires_at>?", (stamp, gate[0], stamp, stamp))
            if used.rowcount == 0:
                return {"resultado": "EN_ESPERA", "proxima_consulta_utc": gate[0]}, None
            authorization = gate[0]
        db.execute("INSERT OR REPLACE INTO policy VALUES(1,?)", (iso(now + INTERVAL),))
        return None, authorization

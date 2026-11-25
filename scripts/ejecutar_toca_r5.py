"""Run the Toca collector without a console and keep a log for each execution."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import mkdtemp
import traceback


def utc_now():
    return datetime.now(timezone.utc)


def run(directory, command, workspace):
    logs = directory / "pronostico-toca-ejecuciones"
    logs.mkdir(parents=True, exist_ok=True)
    start = utc_now()
    attempt = Path(mkdtemp(prefix=start.strftime("%Y%m%dT%H%M%SZ-"), dir=logs))
    metadata = {"inicio_utc": start.isoformat(), "cwd": str(workspace), "directorio_datos": str(directory),
                "launcher": sys.executable, "comando": command}
    report = attempt / "ejecucion.json"
    report.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    code = 1
    try:
        with (attempt / "stdout.log").open("wb") as stdout, (attempt / "stderr.log").open("wb") as stderr:
            try:
                child = subprocess.run(command, cwd=workspace, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                       env={**os.environ, "AGROEDGE_TOCA_TRACE": "1", "PYTHONIOENCODING": "utf-8"},
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=180)
                code = child.returncode
            except (OSError, subprocess.TimeoutExpired):
                stderr.write(traceback.format_exc().encode("utf-8"))
    finally:
        metadata.update(fin_utc=utc_now().isoformat(), codigo_salida=code)
        final_report = attempt / "ejecucion.tmp"
        final_report.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        final_report.replace(report)
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[1]
    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe":
        python = python.with_name("python.exe")
    directory = args.dir.resolve()
    command = [str(python), str(workspace / "scraper" / "toca_forecast.py"), "--dir", str(directory), "fetch"]
    return run(directory, command, workspace)


if __name__ == "__main__":
    sys.exit(main())

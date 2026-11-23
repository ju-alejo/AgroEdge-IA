"""Adapted DataCity serial bridge. Writes normalized envelopes to the local service."""
import argparse
import json
import sys
import time
from pathlib import Path

MAX_LINE = 16384


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, ensure_ascii=True, allow_nan=False), flush=True)


def reject_constant(value):
    raise ValueError(f"Número JSON inválido: {value}")


def forward(line):
    try:
        if len(line) > MAX_LINE:
            raise ValueError("Línea serial demasiado larga.")
        reading = json.loads(line.decode("utf-8"), parse_constant=reject_constant)
        if not isinstance(reading, dict):
            raise ValueError("Cada línea serial debe contener un objeto JSON.")
        emit("reading", reading=reading)
    except (ValueError, UnicodeError) as exc:
        emit("error", error=f"Línea serial rechazada. {exc}")


def read_port(port, baud):
    import serial
    while True:
        try:
            emit("state", state="OPENING")
            with serial.Serial(port, baud, timeout=0.5) as device:
                emit("state", state="OPEN")
                buffer = bytearray()
                discard = False
                while True:
                    chunk = device.read(device.in_waiting or 1)
                    for char in chunk:
                        if char == 10:
                            if not discard and buffer.strip():
                                forward(bytes(buffer).strip())
                            buffer.clear()
                            discard = False
                        elif not discard:
                            buffer.append(char)
                            if len(buffer) > MAX_LINE:
                                emit("error", error="Línea serial demasiado larga.")
                                buffer.clear()
                                discard = True
        except (OSError, serial.SerialException) as exc:
            emit("error", error=f"{port}: {exc}")
            emit("state", state="RECONNECTING")
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--serial", help="Puerto, por ejemplo COM4")
    source.add_argument("--list", action="store_true")
    source.add_argument("--fixture", type=Path, help="Prueba de protocolo, nunca una adquisición real")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    if args.fixture:
        for line in args.fixture.read_bytes().splitlines():
            if line.strip():
                forward(line)
        return
    try:
        if args.list:
            from serial.tools import list_ports
            emit("ports", ports=[{"port": p.device, "description": p.description} for p in list_ports.comports()])
        else:
            read_port(args.serial, args.baud)
    except ImportError:
        emit("error", error="Instala pyserial con python -m pip install -r hardware/requirements.txt.")
        sys.exit(2)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


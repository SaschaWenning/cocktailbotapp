#!/usr/bin/env python3
"""Installed build receipt and root-owned update progress (standard library only)."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

INSTALL_ROOT = Path("/opt/cocktailbot")
STATE_DIR = Path("/var/lib/cocktailbot-update")
LOG_FILE = Path("/var/log/cocktailbot-update.log")


def read_json(path):
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result if isinstance(result, dict) else {}
    except (OSError, ValueError):
        return {}


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".update-")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.write("\n")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def installed_info(root=INSTALL_ROOT, verify=True):
    receipt = read_json(root / "installed.json")
    valid = bool(receipt.get("files")) and bool(receipt.get("installedAt"))
    if verify and valid:
        try:
            valid = all(digest(root / name) == expected for name, expected in receipt["files"].items())
        except (OSError, TypeError):
            valid = False
    return {**receipt, "verified": valid}


def record_install(root=INSTALL_ROOT):
    source = root / "source"
    try:
        sha = subprocess.check_output(["git", "-c", f"safe.directory={source}", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = "local"
    files = ("web/index.html", "web/main.dart.js", "web/flutter_bootstrap.js",
             "raspberry/cocktailbot_server.py", "raspberry/pump_control.py",
             "raspberry/hardware_settings.py", "raspberry/led_ring.py", "raspberry/update_state.py")
    receipt = {"version": (source / "VERSION").read_text().strip(), "sourceSha": sha,
               "installedAt": time.time(), "files": {name: digest(root / name) for name in files}}
    atomic_json(root / "installed.json", receipt)


def boot_id():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unknown"


def write_progress(state, message, directory=STATE_DIR):
    path = directory / "status.json"
    previous = read_json(path)
    now = time.time()
    payload = {"state": "running" if state == "start" else state, "message": message,
               "startedAt": now if state == "start" else previous.get("startedAt", now),
               "updatedAt": now, "bootId": boot_id()}
    atomic_json(path, payload)


def update_status(directory=STATE_DIR, root=INSTALL_ROOT, log_file=LOG_FILE):
    state = read_json(directory / "status.json")
    if not state:
        state = {"state": "idle", "message": "Kein Update gestartet"}
    try:
        unit = subprocess.run(["systemctl", "show", "cocktailbot-self-update.service", "--property=ActiveState", "--value"], capture_output=True, text=True, timeout=2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        unit = "unknown"
    active = unit in {"active", "activating", "reloading", "deactivating"}
    if state.get("state") in {"running", "rebooting"}:
        if state.get("bootId") != boot_id():
            receipt = installed_info(root)
            if state["state"] == "rebooting" and receipt["verified"] and receipt["installedAt"] >= state.get("startedAt", 0):
                state.update(state="complete", message="Update erfolgreich installiert und neu gestartet")
            else:
                state.update(state="failed", message="Update durch Neustart unterbrochen; Installation nicht bestätigt")
        elif unit != "unknown" and not active and time.time() - state.get("updatedAt", 0) > 15:
            state.update(state="failed", message="Update-Prozess wurde beendet. Bitte das Fehlerprotokoll prüfen.")
    try:
        with log_file.open("rb") as stream:
            stream.seek(0, 2)
            stream.seek(max(0, stream.tell() - 6000))
            tail = stream.read().decode("utf-8", errors="replace")
        state["logTail"] = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", tail)
    except OSError:
        state["logTail"] = ""
    return {"ok": True, **state}


def main():
    command, *args = sys.argv[1:]
    if command == "status":
        print(json.dumps(update_status(), ensure_ascii=False))
    elif command == "installed-info":
        print(json.dumps(installed_info()))
    elif command == "record":
        record_install(Path(args[0]) if args else INSTALL_ROOT)
    elif command in {"start", "running", "failed", "rebooting", "complete"}:
        write_progress(command, args[0])
    else:
        raise SystemExit("Unknown update state command")


if __name__ == "__main__":
    main()

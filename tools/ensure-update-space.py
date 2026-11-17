#!/usr/bin/env python3
"""Enlarge an undersized ext4 root filesystem inside its existing partition."""

import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

MINIMUM_FREE = 512 * 1024 * 1024
MINIMUM_GROWTH = 16 * 1024 * 1024


class StorageError(RuntimeError):
    pass


def run(args, timeout=30):
    try:
        return subprocess.run(args, capture_output=True, text=True, check=True,
                              timeout=timeout, env={**os.environ, "LC_ALL": "C"}).stdout.strip()
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise StorageError(f"Speicherprüfung: {args[0]} fehlgeschlagen: {detail}") from exc


def available(path):
    info = os.statvfs(path)
    return info.f_bavail * info.f_frsize


def mount_info(path):
    try:
        result = json.loads(run(["findmnt", "--json", "--target", str(path),
                                 "--output", "SOURCE,FSTYPE,OPTIONS"]))
        return result["filesystems"][0]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise StorageError(f"Mountpunkt für {path} konnte nicht eindeutig ermittelt werden") from exc


def growable_root_device(target):
    target_mount, root_mount = mount_info(target), mount_info("/")
    source = root_mount.get("source", "")
    if (root_mount.get("fstype") != "ext4" or target_mount.get("fstype") != "ext4"
            or not source.startswith("/dev/")
            or "rw" not in root_mount.get("options", "").split(",")
            or os.path.realpath(target_mount.get("source", "")) != os.path.realpath(source)):
        return None
    device = Path(os.path.realpath(source))
    try:
        is_block = stat.S_ISBLK(device.stat().st_mode)
    except OSError as exc:
        raise StorageError(f"Systemlaufwerk {device} ist nicht verfügbar") from exc
    if not is_block or run(["lsblk", "--noheadings", "--output", "TYPE", str(device)]) != "part":
        return None
    return device


def filesystem_bytes(device):
    header = run(["dumpe2fs", "-h", str(device)])
    count = re.search(r"^Block count:\s*(\d+)\s*$", header, re.MULTILINE)
    size = re.search(r"^Block size:\s*(\d+)\s*$", header, re.MULTILINE)
    if not count or not size or int(count[1]) <= 0 or int(size[1]) <= 0:
        raise StorageError("Die tatsächliche ext4-Dateisystemgröße konnte nicht geprüft werden")
    return int(count[1]) * int(size[1])


def progress(message):
    print(f"[CocktailBot Speicher] {message}", flush=True)
    helper = Path("/usr/local/libexec/cocktailbot-update-state")
    if os.getenv("COCKTAILBOT_SELF_UPDATE") == "1" and helper.is_file():
        try:
            subprocess.run([sys.executable, str(helper), "running", message],
                           capture_output=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass


def ensure_space(target=Path("/opt/cocktailbot")):
    free = available(target)
    if free >= MINIMUM_FREE:
        progress(f"{free // (1024 * 1024)} MiB frei; genügend Platz für das Update.")
        return False
    progress("Wenig freier Speicher. Prüfe ungenutzten Platz in der vorhandenen Systempartition.")
    device = growable_root_device(target)
    if device is not None:
        try:
            partition_size = int(run(["blockdev", "--getsize64", str(device)]))
        except ValueError as exc:
            raise StorageError("Die Größe der Systempartition konnte nicht geprüft werden") from exc
        current_size = filesystem_bytes(device)
        if partition_size < current_size:
            raise StorageError("Widersprüchliche Größen von Partition und Dateisystem; automatische Erweiterung abgebrochen")
        if partition_size - current_size >= MINIMUM_GROWTH:
            progress(f"Erweitere ext4-Dateisystem auf {device} auf die vorhandene Partitionsgröße.")
            output = run(["resize2fs", str(device)], timeout=600)
            if output:
                print(output, flush=True)
            free = available(target)
            if free >= MINIMUM_FREE:
                progress(f"Dateisystem erweitert: {free // (1024 * 1024)} MiB frei. Update wird fortgesetzt.")
                return True
    raise StorageError(f"Update abgebrochen: {free // (1024 * 1024)} MiB frei, mindestens 512 MiB erforderlich. "
                       "Keine ausreichende automatische Erweiterung innerhalb der bestehenden ext4-Systempartition möglich.")


def main():
    if os.geteuid() != 0:
        raise SystemExit("Die Speicherprüfung muss als root im Update ausgeführt werden.")
    try:
        ensure_space()
    except (StorageError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

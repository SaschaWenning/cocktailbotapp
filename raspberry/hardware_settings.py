"""Machine-local hardware selection, deliberately separate from browser backups."""

import json
import os
from pathlib import Path


def settings_path() -> Path:
    return Path(os.getenv("COCKTAILBOT_HARDWARE_FILE", "/var/lib/cocktailbot/hardware.json"))


def validate_hardware(value: dict) -> dict[str, str]:
    pump = value.get("pumpDriver")
    led = value.get("ledDriver")
    if pump not in ("relay", "mosfet"):
        raise ValueError("Unbekannte Pumpensteuerung")
    if led not in ("pico", "ring24"):
        raise ValueError("Unbekannter LED-Aufbau")
    return {"pumpDriver": pump, "ledDriver": led}


def load_hardware() -> dict[str, str]:
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"pumpDriver": "relay", "ledDriver": "pico"}
    if not isinstance(value, dict):
        raise ValueError("Ungültige Hardwarekonfiguration")
    # Do not silently revert a MOSFET installation to active-low after corruption.
    return validate_hardware(value)


def save_hardware(value: dict) -> None:
    value = validate_hardware(value)
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value) + "\n", encoding="utf-8")
    temporary.replace(path)

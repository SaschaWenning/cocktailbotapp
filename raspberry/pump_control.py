#!/usr/bin/env python3
"""CocktailBot pump helper: one short-lived process per pump operation."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

PUMP_PINS = {
    17, 18, 27, 22, 23, 24, 25, 4, 5,
    6, 13, 19, 26, 16, 20, 21, 12, 15,
}
MAX_DURATION_MS = 120_000
MOCK_GPIO = os.getenv("COCKTAILBOT_GPIO_MOCK", "0") in {"1", "true", "True"}


class PumpStopRequested(Exception):
    pass


def _resolve_rp1_chip() -> int | None:
    configured = os.getenv("COCKTAILBOT_GPIO_CHIP", "auto").strip().lower()
    if configured and configured != "auto":
        if not configured.isdigit():
            raise RuntimeError(
                "COCKTAILBOT_GPIO_CHIP muss 'auto' oder eine ganze Zahl sein"
            )
        chip = int(configured)
        if not Path(f"/dev/gpiochip{chip}").exists():
            raise RuntimeError(f"/dev/gpiochip{chip} existiert nicht")
        return chip

    try:
        result = subprocess.run(
            ["gpiodetect"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        if "[pinctrl-rp1]" not in line:
            continue
        match = re.match(r"^gpiochip(\d+)\s", line.strip())
        if match:
            chip = int(match.group(1))
            if Path(f"/dev/gpiochip{chip}").exists():
                return chip
    return None


def _signal_stop(_signum: int, _frame: object) -> None:
    raise PumpStopRequested()


def _validate_pin(value: str) -> int:
    try:
        pin = int(value)
    except ValueError as exc:
        raise ValueError("Pin muss eine ganze Zahl sein") from exc
    if pin not in PUMP_PINS:
        raise ValueError(f"GPIO{pin} ist kein CocktailBot-Pumpenpin")
    return pin


def _validate_duration(value: str) -> int:
    try:
        duration_ms = int(value)
    except ValueError as exc:
        raise ValueError("Dauer muss eine ganze Zahl sein") from exc
    if duration_ms < 1 or duration_ms > MAX_DURATION_MS:
        raise ValueError(
            f"Dauer muss zwischen 1 und {MAX_DURATION_MS} ms liegen"
        )
    return duration_ms


if MOCK_GPIO:
    def activate_pump(pin: int, duration_ms: int) -> int:
        del pin
        time.sleep(duration_ms / 1000.0)
        return 0

    def force_off(pin: int) -> int:
        del pin
        return 0

else:
    chip = _resolve_rp1_chip()
    if chip is not None:
        os.environ["RPI_LGPIO_CHIP"] = str(chip)

    try:
        import RPi.GPIO as GPIO
    except ImportError as exc:
        print(
            "RPi.GPIO-Kompatibilitaet fehlt. Installiere python3-rpi-lgpio.",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc

    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    def _safe_high_and_cleanup(pin: int, configured: bool) -> None:
        if configured:
            try:
                GPIO.output(pin, GPIO.HIGH)
            except Exception:
                pass
        try:
            # Dieser Prozess besitzt genau einen Pumpenpin. Das globale cleanup
            # entspricht dadurch der alten pump_control.py.
            GPIO.cleanup()
        except Exception:
            pass

    def activate_pump(pin: int, duration_ms: int) -> int:
        configured = False
        try:
            # Bewusst dieselbe Reihenfolge wie in der alten Software.
            GPIO.setup(pin, GPIO.OUT)
            configured = True
            GPIO.output(pin, GPIO.HIGH)
            GPIO.output(pin, GPIO.LOW)
            time.sleep(duration_ms / 1000.0)
            GPIO.output(pin, GPIO.HIGH)
            return 0
        except PumpStopRequested:
            return 130
        except Exception as exc:
            print(f"Pumpenfehler GPIO{pin}: {exc}", file=sys.stderr)
            return 1
        finally:
            _safe_high_and_cleanup(pin, configured)

    def force_off(pin: int) -> int:
        configured = False
        try:
            GPIO.setup(pin, GPIO.OUT)
            configured = True
            GPIO.output(pin, GPIO.HIGH)
            return 0
        except Exception as exc:
            print(f"Pumpen-AUS-Fehler GPIO{pin}: {exc}", file=sys.stderr)
            return 1
        finally:
            _safe_high_and_cleanup(pin, configured)


def main() -> int:
    if len(sys.argv) < 3:
        print(
            "Verwendung: pump_control.py activate <pin> <duration_ms> | off <pin>",
            file=sys.stderr,
        )
        return 2

    command = sys.argv[1].strip().lower()
    try:
        pin = _validate_pin(sys.argv[2])
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    signal.signal(signal.SIGTERM, _signal_stop)
    signal.signal(signal.SIGINT, _signal_stop)

    if command == "activate":
        if len(sys.argv) != 4:
            print("activate benötigt <pin> <duration_ms>", file=sys.stderr)
            return 2
        try:
            duration_ms = _validate_duration(sys.argv[3])
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        return activate_pump(pin, duration_ms)

    if command == "off":
        if len(sys.argv) != 3:
            print("off benötigt nur <pin>", file=sys.stderr)
            return 2
        return force_off(pin)

    print(f"Unbekannter Befehl: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

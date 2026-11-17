"""24 WS2812B LEDs on Cocktailbot V2: BCM9, physical header pin 21.

Pi 5 uses RP1 PIO, not software bit-banging or the SPI MOSI pin (BCM10).
The hardware dependency is imported only when the ring is selected.
"""

import os
import threading
import time
from pathlib import Path


class RingLedController:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._write = None
        self._free = None
        self._pin = None
        self._closed = False
        self.port = "GPIO9 / Pin 21"
        self.last_command = ""
        self.last_response = ""
        self.last_error = ""
        self._mode = "OFF"
        self._color = (0, 0, 0)
        self._brightness = 89 / 255
        self._started = time.monotonic()
        self._mock = os.getenv("COCKTAILBOT_GPIO_MOCK", "0") in {"1", "true", "True"}

    def _connect(self) -> None:
        if self._write is not None:
            return
        if self._closed:
            raise RuntimeError("LED-Steuerung ist geschlossen")
        if self._mock:
            self._write = lambda pin, data: None
        else:
            if not Path("/dev/pio0").exists():
                raise RuntimeError("24-LED-Ring benötigt Raspberry Pi 5 mit /dev/pio0; Raspberry Pi OS aktualisieren und neu starten.")
            import board
            from adafruit_raspberry_pi5_neopixel_write import neopixel_write, free_pio
            self._pin = board.D9
            self._free = free_pio
            self._write = neopixel_write
        try:
            self._write(self._pin, bytes(24 * 3))
        except Exception:
            self._write = None
            if self._free is not None:
                self._free()
            raise
        self._thread = threading.Thread(target=self._animate, name="cocktailbot-ring24", daemon=True)
        self._thread.start()

    @staticmethod
    def _wheel(pos):
        pos %= 256
        if pos < 85:
            return pos * 3, 255 - pos * 3, 0
        if pos < 170:
            pos -= 85
            return 255 - pos * 3, 0, pos * 3
        pos -= 170
        return 0, pos * 3, 255 - pos * 3

    def _frame(self, elapsed):
        colors = [self._color] * 24
        factor = self._brightness
        if self._mode == "OFF":
            factor = 0
        elif self._mode == "RAINBOW":
            colors = [self._wheel(i * 256 // 24 + int(elapsed / .018)) for i in range(24)]
        elif self._mode == "PULSE":
            factor *= 1 - abs((elapsed % 2) - 1)
        elif self._mode in {"BLINK", "BUSY", "ERROR"}:
            factor *= int(elapsed / .3) % 2 == 0
        # WS2812B wire order is GRB, not RGB.
        return bytes(int(c * factor) for r, g, b in colors for c in (g, r, b))

    def _animate(self):
        while not self._stop.wait(.02):
            with self._lock:
                try:
                    self._write(self._pin, self._frame(time.monotonic() - self._started))
                except Exception as exc:
                    self.last_error = str(exc)
                    self._stop.set()

    def send(self, command: str) -> bool:
        with self._lock:
            try:
                if self._stop.is_set():
                    raise RuntimeError(self.last_error or "LED-Steuerung ist gestoppt")
                self._connect()
                parts = command.split()
                action = parts[0]
                if action == "BRIGHT":
                    self._brightness = max(0, min(255, int(parts[1]))) / 255
                else:
                    if action in {"COLOR", "PULSE", "BLINK"}:
                        self._color = tuple(max(0, min(255, int(v))) for v in parts[1:4])
                        if len(self._color) != 3:
                            raise ValueError("Drei Farbwerte erforderlich")
                    elif action in {"READY", "BUSY", "ERROR"}:
                        self._color = {"READY": (0, 255, 0), "BUSY": (255, 255, 0), "ERROR": (255, 0, 0)}[action]
                    elif action not in {"OFF", "RAINBOW"}:
                        raise ValueError("Unbekannter Ring-Befehl")
                    self._mode = "COLOR" if action == "READY" else action
                    self._started = time.monotonic()
                self._write(self._pin, self._frame(time.monotonic() - self._started))
                self.last_command = command
                self.last_response = "OK"
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = str(exc)
                return False

    def apply_idle(self, settings: dict) -> bool:
        r, g, b = (int(settings.get(c, 0)) for c in ("r", "g", "b"))
        command = {"solid": f"COLOR {r} {g} {b}", "rainbow": "RAINBOW",
                   "breathe": f"PULSE {r} {g} {b}", "blink": f"BLINK {r} {g} {b}",
                   "chase": f"BLINK {r} {g} {b}", "off": "OFF"}.get(settings.get("mode"), "OFF")
        return self.send(f"BRIGHT {settings.get('brightness', 89)}") and self.send(command)

    @property
    def connected(self) -> bool:
        return self._write is not None and not self._stop.is_set() and not self.last_error

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            try:
                if self._write is not None:
                    self._write(self._pin, bytes(24 * 3))
            except Exception:
                pass
            finally:
                if self._free is not None:
                    try:
                        self._free()
                    except Exception:
                        pass
                self._closed = True
                self._write = None

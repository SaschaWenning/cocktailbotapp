"""Run with: python -m unittest discover -s raspberry -p 'test_*.py'."""

import importlib.util
import json
import os
from pathlib import Path
import runpy
import tempfile
import types
import unittest
from unittest.mock import patch

os.environ["COCKTAILBOT_GPIO_MOCK"] = "1"

import hardware_settings
import cocktailbot_server as server
from led_ring import RingLedController


class HardwareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "hardware.json"
        self.environment = patch.dict(os.environ, {
            "COCKTAILBOT_HARDWARE_FILE": str(self.path),
            "COCKTAILBOT_GPIO_MOCK": "1",
            "COCKTAILBOT_ACTIVE_HIGH": "0",
        })
        self.environment.start()
        self.paths = patch.multiple(server,
            STATE_FILE=Path(self.temp.name) / "machine.json",
            PAYPAL_DB_FILE=Path(self.temp.name) / "payment.sqlite",
            NETWORK_ACCESS_FILE=Path(self.temp.name) / "network.json",
            RENTAL_ACCESS_FILE=Path(self.temp.name) / "rental.json",
        )
        self.paths.start()
        self.controller = server.PumpController()
        self.app = server.create_app(self.controller, Path(self.temp.name)).test_client()

    def tearDown(self):
        self.controller.close()
        self.paths.stop()
        self.environment.stop()
        self.temp.cleanup()

    def command(self, **data):
        return self.app.post("/api/command", json={"action": "set_hardware", **data})

    def test_existing_defaults_and_no_gpio_claim_at_startup(self):
        self.assertEqual(self.controller.hardware, {"pumpDriver": "relay", "ledDriver": "pico"})
        self.assertFalse(self.path.exists())
        self.assertEqual(self.controller._pump_environment()["COCKTAILBOT_ACTIVE_HIGH"], "0")

    def test_switch_persist_restart_and_switch_back(self):
        response = self.command(pumpDriver="mosfet", ledDriver="ring24", powerDisconnected=True)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(self.controller._pump_environment()["COCKTAILBOT_ACTIVE_HIGH"], "1")
        status = self.app.get("/api/status").json
        self.assertEqual(status["ledController"], "Ring24-GPIO9")
        self.assertTrue(status["ledConnected"])
        self.assertFalse(status["picoConnected"])
        self.controller.close()
        self.controller = server.PumpController()
        self.assertEqual(self.controller.hardware, {"pumpDriver": "mosfet", "ledDriver": "ring24"})
        self.controller.configure_hardware({"pumpDriver": "relay", "ledDriver": "pico"})
        self.assertEqual(self.controller._pump_environment()["COCKTAILBOT_ACTIVE_HIGH"], "0")

    def test_no_switch_while_busy_and_no_implicit_power_confirmation(self):
        self.assertEqual(self.command(pumpDriver="mosfet", ledDriver="pico").status_code, 400)
        self.controller._job = server.PumpJob("test", "sequential", (), 100)
        response = self.command(pumpDriver="mosfet", ledDriver="pico", powerDisconnected=True)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.controller.hardware["pumpDriver"], "relay")
        self.assertFalse(self.path.exists())

    def test_invalid_or_incomplete_settings_are_not_saved(self):
        for data in ({"pumpDriver": "anything", "ledDriver": "pico"}, {"ledDriver": "ring24"}):
            response = self.command(**data, powerDisconnected=True)
            self.assertEqual(response.status_code, 400)
        self.assertFalse(self.path.exists())

    def test_missing_pio_does_not_persist_ring_or_break_pumps(self):
        with patch.dict(os.environ, {"COCKTAILBOT_GPIO_MOCK": "0"}), patch("led_ring.Path.exists", return_value=False):
            response = self.command(pumpDriver="mosfet", ledDriver="ring24", powerDisconnected=True)
        self.assertEqual(response.status_code, 400)
        self.assertIn("/dev/pio0", response.json["error"])
        self.assertEqual(self.controller.hardware["pumpDriver"], "relay")
        self.assertFalse(self.path.exists())
        self.assertEqual(self.app.get("/api/status").status_code, 200)

    def test_corrupt_config_does_not_silently_enable_wrong_polarity(self):
        self.path.write_text('{"ledDriver":"pico"}')
        with self.assertRaises(ValueError):
            hardware_settings.load_hardware()

    def test_saved_ring_without_driver_keeps_mosfet_polarity_and_api_available(self):
        hardware_settings.save_hardware({"pumpDriver": "mosfet", "ledDriver": "ring24"})
        self.controller.close()
        with patch.dict(os.environ, {"COCKTAILBOT_GPIO_MOCK": "0"}), patch("led_ring.Path.exists", return_value=False):
            self.controller = server.PumpController()
        self.assertEqual(self.controller._pump_environment()["COCKTAILBOT_ACTIVE_HIGH"], "1")
        self.assertFalse(self.controller.pico.connected)
        self.assertIn("/dev/pio0", self.controller.pico.last_error)

    def test_selected_polarity_reaches_activation_and_emergency_fallback(self):
        self.controller.configure_hardware({"pumpDriver": "mosfet", "ledDriver": "pico"})
        process = types.SimpleNamespace(poll=lambda: 0, stderr=None)
        with patch.object(server.PUMP_HELPER.__class__, "is_file", return_value=True), patch.object(server.subprocess, "Popen", return_value=process) as launch:
            self.controller._start_pump_process_locked(1, 100)
            self.assertEqual(launch.call_args.kwargs["env"]["COCKTAILBOT_ACTIVE_HIGH"], "1")
        with patch.object(server.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as fallback:
            self.controller._force_off_fallback(1)
            self.assertEqual(fallback.call_args.kwargs["env"]["COCKTAILBOT_ACTIVE_HIGH"], "1")


class PumpPolarityTests(unittest.TestCase):
    def helper(self, active_high, failure=False):
        gpio = types.ModuleType("RPi.GPIO")
        gpio.HIGH, gpio.LOW, gpio.BCM, gpio.OUT = 1, 0, 11, 0
        calls = []
        gpio.setmode = lambda *a: None
        gpio.setwarnings = lambda *a: None
        gpio.setup = lambda pin, mode, **kw: calls.append(("setup", pin, kw["initial"]))
        gpio.output = lambda pin, level: calls.append(("output", pin, level))
        gpio.cleanup = lambda: calls.append(("cleanup",))
        rpi = types.ModuleType("RPi")
        rpi.GPIO = gpio
        with patch.dict(os.environ, {"COCKTAILBOT_GPIO_MOCK": "0", "COCKTAILBOT_ACTIVE_HIGH": str(active_high)}), patch.dict("sys.modules", {"RPi": rpi, "RPi.GPIO": gpio}), patch("subprocess.run", side_effect=OSError), patch("time.sleep", side_effect=RuntimeError("test") if failure else None):
            module = runpy.run_path(str(Path(__file__).with_name("pump_control.py")), run_name="pump_test")
            result = module["activate_pump"](17, 10)
            off = 0 if active_high else 1
            on = 1 - off
            self.assertEqual(calls[0], ("setup", 17, off))
            self.assertEqual(calls[1], ("output", 17, on))
            self.assertEqual(calls[-2:], [("output", 17, off), ("cleanup",)])
            self.assertEqual(result, 1 if failure else 0)
            calls.clear()
            module["force_off"](17)
            self.assertTrue(all(call[2] == off for call in calls if len(call) == 3))

    def test_relay_and_mosfet_normal_and_failure_cleanup(self):
        for active_high in (0, 1):
            for failure in (False, True):
                with self.subTest(active_high=active_high, failure=failure):
                    self.helper(active_high, failure)


class RingTests(unittest.TestCase):
    def test_grb_brightness_and_animation_frames(self):
        ring = RingLedController()
        self.assertTrue(ring.send("BRIGHT 255"))
        self.assertTrue(ring.send("COLOR 255 0 0"))
        self.assertEqual(ring._frame(0), bytes([0, 255, 0]) * 24)
        self.assertTrue(ring.send("BLINK 0 0 255"))
        self.assertEqual(ring._frame(.31), bytes(72))
        self.assertEqual(ring._frame(.01), bytes([0, 0, 255]) * 24)
        self.assertTrue(ring.send("READY"))
        self.assertEqual(ring._frame(0), bytes([255, 0, 0]) * 24)
        self.assertTrue(ring.send("RAINBOW"))
        self.assertNotEqual(ring._frame(0), ring._frame(.2))
        ring.close()
        self.assertFalse(ring.connected)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import update_state


class InstalledBuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "source").mkdir()
        (self.root / "source/VERSION").write_text("2.6")
        for name in ("web/index.html", "web/main.dart.js", "web/flutter_bootstrap.js",
                     "raspberry/cocktailbot_server.py", "raspberry/pump_control.py",
                     "raspberry/hardware_settings.py", "raspberry/led_ring.py", "raspberry/update_state.py"):
            path = self.root / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("installed version")

    def tearDown(self):
        self.temp.cleanup()

    def record(self):
        with patch("update_state.subprocess.check_output", return_value="a" * 40):
            update_state.record_install(self.root)

    def test_downloaded_sources_alone_never_claim_installation(self):
        self.assertFalse(update_state.installed_info(self.root)["verified"])

    def test_failed_build_keeps_previously_installed_version(self):
        self.record()
        (self.root / "source/VERSION").write_text("2.7")
        receipt = update_state.installed_info(self.root)
        self.assertTrue(receipt["verified"])
        self.assertEqual(receipt["version"], "2.6")
        self.assertEqual(receipt["sourceSha"], "a" * 40)

    def test_replaced_web_or_runtime_invalidates_old_receipt(self):
        self.record()
        (self.root / "web/main.dart.js").write_text("different web build")
        self.assertFalse(update_state.installed_info(self.root)["verified"])
        self.record()
        (self.root / "raspberry/cocktailbot_server.py").unlink()
        self.assertFalse(update_state.installed_info(self.root)["verified"])

    def test_progress_failure_and_full_disk_log_are_visible(self):
        directory = self.root / "update"
        log = self.root / "update.log"
        log.write_text("No space left on device")
        with patch("update_state.boot_id", return_value="boot-a"), patch("update_state.subprocess.run", return_value=SimpleNamespace(stdout="inactive")):
            update_state.write_progress("start", "Starting", directory)
            update_state.write_progress("failed", "Installation failed", directory)
            status = update_state.update_status(directory, self.root, log)
        self.assertEqual(status["state"], "failed")
        self.assertIn("No space left on device", status["logTail"])

    def test_successful_restart_requires_installed_receipt(self):
        directory = self.root / "update"
        with patch("update_state.boot_id", return_value="boot-a"):
            update_state.write_progress("start", "Starting", directory)
            self.record()
            update_state.write_progress("rebooting", "Restart", directory)
        with patch("update_state.boot_id", return_value="boot-b"), patch("update_state.subprocess.run", return_value=SimpleNamespace(stdout="inactive")):
            self.assertEqual(update_state.update_status(directory, self.root)["state"], "complete")
            (self.root / "installed.json").unlink()
            self.assertEqual(update_state.update_status(directory, self.root)["state"], "failed")

    def test_killed_or_interrupted_update_does_not_report_success(self):
        directory = self.root / "update"
        with patch("update_state.boot_id", return_value="boot-a"), patch("update_state.time.time", return_value=time.time() - 60):
            update_state.write_progress("start", "Starting", directory)
        with patch("update_state.boot_id", return_value="boot-a"), patch("update_state.subprocess.run", return_value=SimpleNamespace(stdout="inactive")):
            self.assertEqual(update_state.update_status(directory, self.root)["state"], "failed")
        with patch("update_state.boot_id", return_value="boot-b"), patch("update_state.subprocess.run", return_value=SimpleNamespace(stdout="inactive")):
            self.assertEqual(update_state.update_status(directory, self.root)["state"], "failed")


if __name__ == "__main__":
    unittest.main()

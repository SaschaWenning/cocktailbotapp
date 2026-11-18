import concurrent.futures
import io
from pathlib import Path
import time
import unittest
from unittest.mock import Mock, patch

import cocktailbot_server as server
from led_ring import RingLedController
import test_hardware


class Performance28Tests(unittest.TestCase):
    def setUp(self):
        test_hardware.HardwareTests.setUp(self)
        self.state_patch = patch.object(server, "APP_STATE_FILE", Path(self.temp.name) / "app.json")
        self.state_patch.start()

    def tearDown(self):
        test_hardware.HardwareTests.tearDown(self)
        self.state_patch.stop()

    def submit(self, process):
        with patch.object(server.PUMP_HELPER.__class__, "is_file", return_value=True), patch.object(server.subprocess, "Popen", return_value=process):
            response = self.app.post("/api/command", json={"action": "run_pump", "pump": 1, "durationMs": 20})
            self.assertEqual(response.status_code, 202, response.json)
            job_id = response.json["jobId"]
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                result = self.app.get(f"/api/jobs/{job_id}").json
                if result["jobState"] != "running":
                    return job_id, result
                time.sleep(.005)
        self.fail("Job did not finish")

    def test_fast_failure_is_retained_after_idle_and_next_job(self):
        failed = Mock()
        failed.poll.return_value = 1
        failed.stderr = io.StringIO("GPIO failed")
        job_id, result = self.submit(failed)
        self.assertEqual(result["jobState"], "failed")
        self.assertIn("GPIO failed", result["jobError"])
        self.assertFalse(result["busy"])
        success = Mock()
        success.poll.return_value = 0
        success.stderr = io.StringIO("")
        next_id, next_result = self.submit(success)
        self.assertNotEqual(next_id, job_id)
        self.assertEqual(next_result["jobState"], "succeeded")
        self.assertEqual(self.app.get(f"/api/jobs/{job_id}").json["jobState"], "failed")

    def test_stopped_job_is_cancelled_and_unknown_job_is_not_success(self):
        process = Mock()
        process.poll.return_value = None
        process.stderr = io.StringIO("")
        process.terminate.side_effect = lambda: setattr(process.poll, "return_value", 130)
        with patch.object(server.PUMP_HELPER.__class__, "is_file", return_value=True), patch.object(server.subprocess, "Popen", return_value=process):
            response = self.app.post("/api/command", json={"action": "run_pump", "pump": 1, "durationMs": 1000})
            self.app.post("/api/command", json={"action": "stop"})
        result = self.app.get(f"/api/jobs/{response.json['jobId']}").json
        self.assertEqual(result["jobState"], "cancelled")
        self.assertEqual(self.app.get("/api/jobs/missing").status_code, 404)

    def test_compact_status_excludes_configuration_payload(self):
        self.controller.machine_state = {"pumps": ["large snapshot"]}
        self.assertIn("machineState", self.app.get("/api/status").json)
        compact = self.app.get("/api/status?compact=1").json
        self.assertNotIn("machineState", compact)
        self.assertNotIn("pumpPins", compact)
        self.assertIn("hardware", compact)

    def test_thread_start_failure_is_terminal_instead_of_stuck_busy(self):
        with patch.object(server.threading.Thread, "start", side_effect=RuntimeError("no worker")):
            response = self.app.post("/api/command", json={"action": "run_pump", "pump": 1, "durationMs": 20})
        result = self.app.get(f"/api/jobs/{response.json['jobId']}").json
        self.assertEqual(result["jobState"], "failed")
        self.assertFalse(result["busy"])
        self.assertIn("no worker", result["jobError"])

    def test_concurrent_patches_retain_unrelated_data(self):
        server.save_app_state({"recipes": ["recipe"], "pumps": ["pump"], "_lanUsageEventIds": ["event"]})
        application = self.app.application
        def write(change):
            with application.test_client() as client:
                return client.post("/api/app-state/patch", json={"changes": change}).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(write, [{"homeTabs": ["fill", "settings"]}, {"darkMode": False}])), [200, 200])
        state = server.load_app_state()
        self.assertEqual(state["recipes"], ["recipe"])
        self.assertEqual(state["pumps"], ["pump"])
        self.assertEqual(state["homeTabs"], ["fill", "settings"])
        self.assertFalse(state["darkMode"])
        self.assertEqual(state["_lanUsageEventIds"], ["event"])
        self.assertEqual(list(Path(self.temp.name).glob(".app-state-*")), [])

    def test_patch_rejects_private_and_internal_keys(self):
        for key in ("settingsPassword", "rentalServicePin", "_lanUsageEventIds"):
            self.assertEqual(self.app.post("/api/app-state/patch", json={"changes": {key: "bad"}}).status_code, 400)

    def test_static_cache_revalidates_etag_while_api_and_bootstrap_stay_fresh(self):
        root = Path(self.temp.name)
        for filename in ("index.html", "flutter_bootstrap.js", "main.dart.js"):
            (root / filename).write_text("version one")
        response = self.app.get("/main.dart.js")
        self.assertIn("no-cache", response.headers["Cache-Control"])
        self.assertNotIn("no-store", response.headers["Cache-Control"])
        etag = response.headers["ETag"]
        response.close()
        cached = self.app.get("/main.dart.js", headers={"If-None-Match": etag})
        self.assertEqual(cached.status_code, 304)
        cached.close()
        (root / "main.dart.js").write_text("version two with new code")
        with self.app.get("/main.dart.js", headers={"If-None-Match": etag}) as changed:
            self.assertEqual(changed.status_code, 200)
        for path in ("/", "/flutter_bootstrap.js", "/api/status"):
            with self.app.get(path) as fresh:
                self.assertIn("no-store", fresh.headers["Cache-Control"])

    def test_static_led_color_is_not_written_again(self):
        ring = RingLedController()
        try:
            self.assertTrue(ring.send("COLOR 255 0 0"))
            writer = Mock()
            ring._write = writer
            self.assertTrue(ring.send("COLOR 255 0 0"))
            time.sleep(.08)
            writer.assert_not_called()
            self.assertTrue(ring.send("OFF"))
            self.assertEqual(writer.call_count, 1)
            self.assertTrue(ring.send("OFF"))
            self.assertEqual(writer.call_count, 1)
        finally:
            ring.close()


if __name__ == "__main__":
    unittest.main()

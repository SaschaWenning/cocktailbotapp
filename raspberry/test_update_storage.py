"""Storage preflight tests use fake devices and never resize a real filesystem."""

import importlib.util
from pathlib import Path
import stat
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("update_storage", Path(__file__).resolve().parents[1] / "tools/ensure-update-space.py")
storage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(storage)
GIB = 1024 ** 3
MIB = 1024 ** 2


class UpdateStorageTests(unittest.TestCase):
    def setUp(self):
        self.progress = patch.object(storage, "progress").start()
        self.addCleanup(patch.stopall)
        self.device = Path("/dev/mmcblk0p2")

    def test_sufficient_space_does_not_inspect_or_resize_device(self):
        with patch.object(storage, "available", return_value=512 * MIB), patch.object(storage, "growable_root_device") as inspect:
            self.assertFalse(storage.ensure_space())
            inspect.assert_not_called()

    def test_8_gib_filesystem_on_118_gib_partition_expands_then_continues(self):
        with patch.object(storage, "available", side_effect=[307 * MIB, 110 * GIB]), patch.object(storage, "growable_root_device", return_value=self.device), patch.object(storage, "filesystem_bytes", return_value=8 * GIB), patch.object(storage, "run", side_effect=[str(118 * GIB), ""]) as command:
            self.assertTrue(storage.ensure_space())
            self.assertEqual(command.call_args_list[1].args[0], ["resize2fs", str(self.device)])
            self.assertIn("Update wird fortgesetzt", self.progress.call_args.args[0])

    def test_truly_full_partition_is_not_resized(self):
        with patch.object(storage, "available", return_value=307 * MIB), patch.object(storage, "growable_root_device", return_value=self.device), patch.object(storage, "filesystem_bytes", return_value=8 * GIB), patch.object(storage, "run", return_value=str(8 * GIB)) as command:
            with self.assertRaises(storage.StorageError):
                storage.ensure_space()
            self.assertEqual(command.call_count, 1)

    def test_resize_error_is_not_reported_as_success(self):
        with patch.object(storage, "available", return_value=307 * MIB), patch.object(storage, "growable_root_device", return_value=self.device), patch.object(storage, "filesystem_bytes", return_value=8 * GIB), patch.object(storage, "run", side_effect=[str(118 * GIB), storage.StorageError("resize failed")]):
            with self.assertRaisesRegex(storage.StorageError, "resize failed"):
                storage.ensure_space()

    def test_insufficient_space_after_growth_still_aborts(self):
        with patch.object(storage, "available", return_value=307 * MIB), patch.object(storage, "growable_root_device", return_value=self.device), patch.object(storage, "filesystem_bytes", return_value=8 * GIB), patch.object(storage, "run", side_effect=[str(118 * GIB), ""]):
            with self.assertRaisesRegex(storage.StorageError, "512 MiB"):
                storage.ensure_space()

    def test_partition_smaller_than_filesystem_aborts(self):
        with patch.object(storage, "available", return_value=307 * MIB), patch.object(storage, "growable_root_device", return_value=self.device), patch.object(storage, "filesystem_bytes", return_value=118 * GIB), patch.object(storage, "run", return_value=str(8 * GIB)) as command:
            with self.assertRaisesRegex(storage.StorageError, "Widersprüchliche"):
                storage.ensure_space()
            self.assertEqual(command.call_count, 1)

    def test_other_filesystems_mounts_and_read_only_root_are_untouched(self):
        valid = {"source": "/dev/mmcblk0p2", "fstype": "ext4", "options": "rw,relatime"}
        cases = [
            ({**valid, "fstype": "btrfs"}, {**valid, "fstype": "btrfs"}),
            ({**valid, "source": "/dev/sda1"}, valid),
            ({**valid, "options": "ro"}, {**valid, "options": "ro"}),
        ]
        for target, root in cases:
            with self.subTest(target=target), patch.object(storage, "mount_info", side_effect=[target, root]), patch.object(storage, "run") as command:
                self.assertIsNone(storage.growable_root_device(Path("/opt/cocktailbot")))
                command.assert_not_called()

    def test_root_partition_is_accepted_but_lvm_device_is_not(self):
        mount = {"source": "/dev/mmcblk0p2", "fstype": "ext4", "options": "rw,relatime"}
        for kind in ("part", "lvm"):
            with self.subTest(kind=kind), patch.object(storage, "mount_info", return_value=mount), patch.object(Path, "stat", return_value=SimpleNamespace(st_mode=stat.S_IFBLK)), patch.object(storage, "run", return_value=kind):
                result = storage.growable_root_device(Path("/opt/cocktailbot"))
                self.assertEqual(result is not None, kind == "part")

    def test_actual_ext4_size_is_read_from_superblock(self):
        with patch.object(storage, "run", return_value="Block count:  2097152\nBlock size:  4096\n"):
            self.assertEqual(storage.filesystem_bytes(self.device), 8 * GIB)
        with patch.object(storage, "run", return_value="invalid output"):
            with self.assertRaises(storage.StorageError):
                storage.filesystem_bytes(self.device)

    def test_missing_tool_has_an_actionable_error(self):
        with patch.object(storage.subprocess, "run", side_effect=FileNotFoundError("not installed")):
            with self.assertRaisesRegex(storage.StorageError, "resize2fs fehlgeschlagen"):
                storage.run(["resize2fs", str(self.device)])


if __name__ == "__main__":
    unittest.main()

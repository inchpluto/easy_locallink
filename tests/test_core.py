import hashlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from locallink.core import TransferStore, human_size, network_diagnostics, safe_filename
from locallink.__main__ import find_adb


class CoreTests(unittest.TestCase):
    def test_safe_filename_blocks_traversal(self):
        self.assertEqual(safe_filename("../../secret.txt"), "secret.txt")
        self.assertEqual(safe_filename(r"C:\\temp\\bad?.txt"), "bad_.txt")
        self.assertEqual(safe_filename("..."), "unnamed-file")

    def test_human_size(self):
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(1536), "1.5 KB")

    def test_loopback_diagnostic_is_safe(self):
        result = network_diagnostics("127.0.0.1")
        self.assertEqual(result["lan_state"], "unknown")
        self.assertIn("vpn_detected", result)

    def test_find_adb_uses_standard_android_sdk_location(self):
        with patch("locallink.__main__.shutil.which", return_value=None), patch.dict(
            "os.environ", {"LOCALAPPDATA": r"C:\Users\tester\AppData\Local"}, clear=True
        ), patch("locallink.__main__.Path.is_file", return_value=True):
            self.assertTrue(find_adb().endswith(r"Android\Sdk\platform-tools\adb.exe"))

    def test_store_text_and_file_persists(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            store = TransferStore(root)
            text = store.add_text("hello", "phone")
            payload = b"binary payload"
            file = store.save_file(
                io.BytesIO(payload),
                "demo.bin",
                len(payload),
                "pc",
                hashlib.sha256(payload).hexdigest(),
            )
            self.assertEqual(store.path_for(file).read_bytes(), payload)
            restored = TransferStore(root)
            self.assertEqual([item["id"] for item in restored.list()], [file.id, text.id])
            self.assertEqual(restored.clear(), 2)
            self.assertEqual(restored.list(), [])
            self.assertEqual(list(restored.files.iterdir()), [])

    def test_store_rejects_bad_hash_and_cleans_partial(self):
        with tempfile.TemporaryDirectory() as folder:
            store = TransferStore(Path(folder))
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                store.save_file(io.BytesIO(b"abc"), "a.txt", 3, "pc", "0" * 64)
            self.assertEqual(list(store.files.iterdir()), [])

    def test_store_list_adds_platform_file_capabilities(self):
        with tempfile.TemporaryDirectory() as folder:
            store = TransferStore(Path(folder))
            payload = b"fake presentation"
            store.save_file(io.BytesIO(payload), "slides.pptx", len(payload), "phone")
            item = store.list(platform="windows", converter_available=True)[0]
            self.assertEqual(item["category"], "presentation")
            self.assertEqual(item["actions"], ["preview_convert", "open_external", "download"])

    def test_store_text_records_expose_inline_preview(self):
        with tempfile.TemporaryDirectory() as folder:
            store = TransferStore(Path(folder))
            store.add_text("hello", "phone")
            item = store.list(platform="android")[0]
            self.assertEqual(item["category"], "text")
            self.assertEqual(item["actions"], ["preview_inline"])


if __name__ == "__main__":
    unittest.main()

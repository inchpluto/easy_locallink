import tempfile
import time
import unittest
from pathlib import Path

from locallink.core import TransferRecord
from locallink.preview import OfficePreviewService, PreviewError


class FakeConverter:
    def __init__(self, pdf_bytes=b"%PDF-1.4\npreview"):
        self.pdf_bytes = pdf_bytes
        self.calls = 0

    def convert(self, source: Path, target: Path, profile_dir: Path, timeout: int) -> None:
        self.calls += 1
        target.write_bytes(self.pdf_bytes)


class FailingConverter:
    def convert(self, source, target, profile_dir, timeout):
        target.write_bytes(b"partial")
        raise RuntimeError("conversion failed")


def record_for(source: Path, identifier="record-1") -> TransferRecord:
    return TransferRecord(
        id=identifier,
        kind="file",
        name=source.name,
        size=source.stat().st_size,
        sha256="0" * 64,
        created_at=1.0,
        sender="Phone",
    )


class OfficePreviewServiceTests(unittest.TestCase):
    """Plain unittest so ``python -m unittest discover`` picks these up."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _office_file(self, name="slides.pptx", payload=b"office") -> Path:
        source = self.tmp_path / name
        source.write_bytes(payload)
        return source

    def test_preview_cache_reuses_pdf_until_source_changes(self):
        converter = FakeConverter()
        service = OfficePreviewService(self.tmp_path / "cache", converter=converter)
        source = self._office_file()
        record = record_for(source)

        first = service.get_or_create(record, source)
        second = service.get_or_create(record, source)
        time.sleep(0.002)
        source.write_bytes(b"office changed")
        changed = service.get_or_create(record_for(source), source)

        self.assertEqual(first.read_bytes(), b"%PDF-1.4\npreview")
        self.assertEqual(first, second)
        self.assertNotEqual(changed, first)
        self.assertEqual(converter.calls, 2)

    def test_preview_rejects_missing_converter(self):
        source = self._office_file()
        service = OfficePreviewService(self.tmp_path / "cache", converter=None)

        with self.assertRaises(PreviewError) as caught:
            service.get_or_create(record_for(source), source)
        self.assertEqual(caught.exception.code, "PREVIEW_UNSUPPORTED")

    def test_preview_rejects_files_over_limit(self):
        source = self._office_file(payload=b"12345")
        service = OfficePreviewService(self.tmp_path / "cache", converter=FakeConverter(), max_bytes=4)

        with self.assertRaises(PreviewError) as caught:
            service.get_or_create(record_for(source), source)
        self.assertEqual(caught.exception.code, "PREVIEW_TOO_LARGE")

    def test_preview_wraps_converter_failure_and_removes_partial(self):
        source = self._office_file()
        service = OfficePreviewService(self.tmp_path / "cache", converter=FailingConverter())

        with self.assertRaises(PreviewError) as caught:
            service.get_or_create(record_for(source), source)
        self.assertEqual(caught.exception.code, "PREVIEW_CONVERSION_FAILED")
        self.assertEqual(list((self.tmp_path / "cache").glob("*.part")), [])

    def test_remove_record_clears_all_cached_versions(self):
        source = self._office_file()
        service = OfficePreviewService(self.tmp_path / "cache", converter=FakeConverter())
        service.get_or_create(record_for(source), source)
        (self.tmp_path / "cache" / "record-1-old.pdf").write_bytes(b"old")

        service.remove_record("record-1")

        self.assertEqual(list((self.tmp_path / "cache").glob("record-1-*.pdf")), [])


if __name__ == "__main__":
    unittest.main()

import time
from pathlib import Path

import pytest

from locallink.core import TransferRecord
from locallink.preview import OfficePreviewService, PreviewError


class FakeConverter:
    def __init__(self, pdf_bytes=b"%PDF-1.4\npreview"):
        self.pdf_bytes = pdf_bytes
        self.calls = 0

    def convert(self, source: Path, target: Path, profile_dir: Path, timeout: int) -> None:
        self.calls += 1
        target.write_bytes(self.pdf_bytes)


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


def test_preview_cache_reuses_pdf_until_source_changes(tmp_path):
    converter = FakeConverter()
    service = OfficePreviewService(tmp_path / "cache", converter=converter)
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"office")
    record = record_for(source)

    first = service.get_or_create(record, source)
    second = service.get_or_create(record, source)
    time.sleep(0.002)
    source.write_bytes(b"office changed")
    changed = service.get_or_create(record_for(source), source)

    assert first.read_bytes() == b"%PDF-1.4\npreview"
    assert first == second
    assert changed != first
    assert converter.calls == 2


def test_preview_rejects_missing_converter(tmp_path):
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"office")
    service = OfficePreviewService(tmp_path / "cache", converter=None)

    with pytest.raises(PreviewError, match="PREVIEW_UNSUPPORTED"):
        service.get_or_create(record_for(source), source)


def test_preview_rejects_files_over_limit(tmp_path):
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"12345")
    service = OfficePreviewService(tmp_path / "cache", converter=FakeConverter(), max_bytes=4)

    with pytest.raises(PreviewError, match="PREVIEW_TOO_LARGE"):
        service.get_or_create(record_for(source), source)


def test_preview_wraps_converter_failure_and_removes_partial(tmp_path):
    class FailingConverter:
        def convert(self, source, target, profile_dir, timeout):
            target.write_bytes(b"partial")
            raise RuntimeError("conversion failed")

    source = tmp_path / "slides.pptx"
    source.write_bytes(b"office")
    service = OfficePreviewService(tmp_path / "cache", converter=FailingConverter())

    with pytest.raises(PreviewError, match="PREVIEW_CONVERSION_FAILED"):
        service.get_or_create(record_for(source), source)
    assert list((tmp_path / "cache").glob("*.part")) == []


def test_remove_record_clears_all_cached_versions(tmp_path):
    source = tmp_path / "slides.pptx"
    source.write_bytes(b"office")
    service = OfficePreviewService(tmp_path / "cache", converter=FakeConverter())
    service.get_or_create(record_for(source), source)
    (tmp_path / "cache" / "record-1-old.pdf").write_bytes(b"old")

    service.remove_record("record-1")

    assert list((tmp_path / "cache").glob("record-1-*.pdf")) == []

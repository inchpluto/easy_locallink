import io
from pathlib import Path

from locallink.core import TransferStore
from locallink.native_bridge import NativeFileBridge


def test_bridge_resolves_only_existing_store_records(tmp_path):
    store = TransferStore(tmp_path)
    opened = []
    bridge = NativeFileBridge(store, opener=lambda path: opened.append(path))

    assert bridge.open_record("missing") == {"ok": False, "error": "FILE_NOT_FOUND"}
    assert opened == []


def test_bridge_opens_record_by_id_not_caller_path(tmp_path):
    store = TransferStore(tmp_path)
    record = store.save_file(io.BytesIO(b"hello"), "report.docx", 5, "Phone")
    opened = []
    bridge = NativeFileBridge(store, opener=lambda path: opened.append(path))

    result = bridge.open_record(record.id)

    assert result == {"ok": True}
    assert opened == [store.path_for(record).resolve()]
    assert opened[0].is_relative_to(store.files.resolve())


def test_bridge_rejects_missing_disk_file(tmp_path):
    store = TransferStore(tmp_path)
    record = store.save_file(io.BytesIO(b"x"), "gone.txt", 1, "Phone")
    store.path_for(record).unlink()
    bridge = NativeFileBridge(store, opener=lambda path: None)

    assert bridge.open_record(record.id) == {"ok": False, "error": "FILE_NOT_FOUND"}


def test_bridge_reports_missing_external_viewer(tmp_path):
    store = TransferStore(tmp_path)
    record = store.save_file(io.BytesIO(b"x"), "unknown.bin", 1, "Phone")
    bridge = NativeFileBridge(store, opener=lambda path: (_ for _ in ()).throw(OSError()))

    assert bridge.open_record(record.id) == {"ok": False, "error": "NO_EXTERNAL_VIEWER"}

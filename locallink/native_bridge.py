from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from .core import TransferStore


def _default_open(path: Path) -> None:
    os.startfile(str(path))  # type: ignore[attr-defined]


def _default_reveal(path: Path) -> None:
    subprocess.Popen(["explorer.exe", "/select,", str(path)], close_fds=True)


class NativeFileBridge:
    """Resolve opaque transfer IDs before handing files to Windows."""

    def __init__(
        self,
        store: TransferStore,
        opener: Callable[[Path], object] = _default_open,
        revealer: Callable[[Path], object] = _default_reveal,
    ) -> None:
        self.store = store
        self.opener = opener
        self.revealer = revealer

    def _resolve(self, record_id: str) -> Path | None:
        record = self.store.get(str(record_id))
        if record is None or record.kind != "file":
            return None
        path = self.store.path_for(record).resolve()
        root = self.store.files.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return None
        return path

    def open_record(self, record_id: str) -> dict:
        path = self._resolve(record_id)
        if path is None:
            return {"ok": False, "error": "FILE_NOT_FOUND"}
        try:
            self.opener(path)
        except OSError:
            return {"ok": False, "error": "NO_EXTERNAL_VIEWER"}
        return {"ok": True}

    def reveal_record(self, record_id: str) -> dict:
        path = self._resolve(record_id)
        if path is None:
            return {"ok": False, "error": "FILE_NOT_FOUND"}
        try:
            self.revealer(path)
        except OSError:
            return {"ok": False, "error": "REVEAL_FAILED"}
        return {"ok": True}

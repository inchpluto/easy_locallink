from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .core import TransferRecord


class PreviewError(RuntimeError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def find_libreoffice() -> Path | None:
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    candidates = [
        Path(executable) if executable else None,
        Path(os.environ.get("PROGRAMFILES", "")) / "LibreOffice" / "program" / "soffice.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "LibreOffice" / "program" / "soffice.exe",
    ]
    return next((path.resolve() for path in candidates if path and path.is_file()), None)


class LibreOfficeConverter:
    def __init__(self, executable: Path):
        self.executable = executable.resolve()

    def convert(self, source: Path, target: Path, profile_dir: Path, timeout: int) -> None:
        output_dir = target.parent
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        command = [
            str(self.executable),
            f"-env:UserInstallation={profile_dir.resolve().as_uri()}",
            "--headless",
            "--safe-mode",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(source.resolve()),
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            creationflags=flags,
        )
        generated = output_dir / f"{source.stem}.pdf"
        if result.returncode != 0 or not generated.is_file():
            raise RuntimeError((result.stderr or result.stdout or "LibreOffice 未生成 PDF").strip())
        if generated.resolve() != target.resolve():
            os.replace(generated, target)


class OfficePreviewService:
    def __init__(
        self,
        cache_dir: Path,
        converter=None,
        timeout: int = 60,
        max_bytes: int = 200 * 1024 * 1024,
    ):
        self.cache_dir = cache_dir.resolve()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.converter = converter
        self.timeout = timeout
        self.max_bytes = max_bytes

    @property
    def available(self) -> bool:
        return self.converter is not None

    def get_or_create(self, record: TransferRecord, source: Path) -> Path:
        source = source.resolve()
        if self.converter is None:
            raise PreviewError("PREVIEW_UNSUPPORTED", "未检测到 LibreOffice")
        if not source.is_file():
            raise PreviewError("FILE_NOT_FOUND")
        stat = source.stat()
        if stat.st_size > self.max_bytes:
            raise PreviewError("PREVIEW_TOO_LARGE", "Office 文件超过 200 MB")
        identifier = re.sub(r"[^a-zA-Z0-9_-]", "_", record.id)
        cache = self.cache_dir / f"{identifier}-{stat.st_size}-{stat.st_mtime_ns}.pdf"
        if cache.is_file() and cache.stat().st_size:
            return cache
        part = cache.with_suffix(".pdf.part")
        try:
            with tempfile.TemporaryDirectory(prefix="profile-", dir=self.cache_dir) as profile:
                self.converter.convert(source, part, Path(profile), self.timeout)
            if not part.is_file() or not part.stat().st_size:
                raise RuntimeError("转换结果为空")
            os.replace(part, cache)
            return cache
        except PreviewError:
            raise
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            part.unlink(missing_ok=True)
            raise PreviewError("PREVIEW_CONVERSION_FAILED", str(exc)) from exc

    def remove_record(self, identifier: str) -> None:
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", identifier)
        for path in self.cache_dir.glob(f"{clean}-*.pdf"):
            path.unlink(missing_ok=True)

"""Deterministic Windows runtime selection for PyInstaller specs."""
from pathlib import Path
import importlib.util


def fix_windows_runtime(binaries):
    # Qt 6 uses the unversioned Windows ICU API. Conda/Poppler's same-name
    # ICU has version-suffixed exports and must never shadow System32 ICU.
    spec = importlib.util.find_spec('PySide6')
    qt = Path(spec.origin).parent if spec and spec.origin else None
    runtime_names = {'vcruntime140.dll', 'vcruntime140_1.dll'}
    result = []
    for destination, source, kind in binaries:
        name = Path(destination).name.lower()
        if name in {'icuuc.dll', 'icuin.dll', 'icudt78.dll'}:
            continue
        if qt is not None and name in runtime_names:
            candidate = qt / name
            if candidate.exists():
                source = str(candidate)
        result.append((destination, source, kind))
    return result

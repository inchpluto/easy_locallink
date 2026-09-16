import importlib.util
import unittest
from pathlib import Path
from packaging_runtime import fix_windows_runtime

PYSIDE6_AVAILABLE = importlib.util.find_spec('PySide6') is not None


class PackagingRuntimeTests(unittest.TestCase):
    def test_excludes_foreign_icu(self):
        values = [('icuuc.dll', 'foreign/icuuc.dll', 'BINARY'),
                  ('icudt78.dll', 'foreign/icudt78.dll', 'BINARY'),
                  ('PySide6/Qt6Core.dll', 'qt/Qt6Core.dll', 'BINARY')]
        self.assertEqual(fix_windows_runtime(values), values[2:])

    @unittest.skipUnless(PYSIDE6_AVAILABLE, 'PySide6 is only installed in the Windows packaging environment')
    def test_uses_qt_runtime_in_all_locations(self):
        values = [('VCRUNTIME140.dll', 'old/VCRUNTIME140.dll', 'BINARY'),
                  ('PySide6/VCRUNTIME140.dll', 'old/VCRUNTIME140.dll', 'BINARY')]
        fixed = fix_windows_runtime(values)
        self.assertEqual(fixed[0][1], fixed[1][1])
        self.assertTrue(Path(fixed[0][1]).is_file())
        self.assertIn('PySide6', fixed[0][1])

    @unittest.skipIf(PYSIDE6_AVAILABLE, 'only meaningful when the Qt runtime is absent')
    def test_keeps_existing_sources_when_qt_is_missing(self):
        values = [('VCRUNTIME140.dll', 'old/VCRUNTIME140.dll', 'BINARY')]
        fixed = fix_windows_runtime(values)
        # Without PySide6 the original sources must survive untouched instead
        # of raising on a missing spec.
        self.assertEqual(fixed, values)

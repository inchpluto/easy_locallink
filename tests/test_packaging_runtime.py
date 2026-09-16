import unittest
from pathlib import Path
from packaging_runtime import fix_windows_runtime


class PackagingRuntimeTests(unittest.TestCase):
    def test_excludes_foreign_icu(self):
        values = [('icuuc.dll', 'foreign/icuuc.dll', 'BINARY'),
                  ('icudt78.dll', 'foreign/icudt78.dll', 'BINARY'),
                  ('PySide6/Qt6Core.dll', 'qt/Qt6Core.dll', 'BINARY')]
        self.assertEqual(fix_windows_runtime(values), values[2:])

    def test_uses_qt_runtime_in_all_locations(self):
        values = [('VCRUNTIME140.dll', 'old/VCRUNTIME140.dll', 'BINARY'),
                  ('PySide6/VCRUNTIME140.dll', 'old/VCRUNTIME140.dll', 'BINARY')]
        fixed = fix_windows_runtime(values)
        self.assertEqual(fixed[0][1], fixed[1][1])
        self.assertTrue(Path(fixed[0][1]).is_file())
        self.assertIn('PySide6', fixed[0][1])

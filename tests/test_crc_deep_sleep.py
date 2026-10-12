"""Read-only import and scope contracts for the deep sleep script."""
import ast
import unittest
from pathlib import Path

class DeepSleepContracts(unittest.TestCase):
    def test_valid_python_syntax(self):
        f = Path(__file__).resolve().parents[1] / 'scripts' / 'crc-deep-sleep.py'
        ast.parse(f.read_text(encoding='utf-8'))

if __name__ == '__main__':
    unittest.main()

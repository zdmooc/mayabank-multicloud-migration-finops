"""Offline deep sleep contracts: no cluster access."""
import ast
import unittest
from pathlib import Path

FILE = Path(__file__).resolve().parents[1] / "scripts" / "crc-deep-sleep.py"

class DeepSleepContracts(unittest.TestCase):
    def test_python_syntax(self):
        ast.parse(FILE.read_text(encoding="utf-8"))

    def test_explicit_loss_acceptance_and_separate_resume(self):
        src = FILE.read_text(encoding="utf-8")
        for requirement in (
            "CRC_DEEP_PARK", "CRC_ACK_DATA_LOSS", "CRC_ACK_DOWNTIME",
            "CRC_ACK_REBUILD", "CRC_DEEP_RESUME",
            "PARK_PARTIAL", "PARK_RESULT=PASS", "RESUME_RESULT=PASS",
        ):
            self.assertIn(requirement, src)

    def test_bounded_scope_and_pvc_preservation(self):
        src = FILE.read_text(encoding="utf-8")
        for item in ("mayabank-mq-local", "tradeops",
                     "mq-data", "payments-db-data",
                     "payment-processing", "redpanda", "qdrant", "postgres"):
            self.assertIn(item, src)
        self.assertNotIn('m.oc("-n",ns,"delete"', src)

if __name__ == "__main__":
    unittest.main()

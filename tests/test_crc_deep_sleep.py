"""Offline deep sleep contracts: no cluster access."""
import ast
import importlib.util
import unittest
from unittest.mock import patch
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


class RecoveryVerificationTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("deep_sleep_test", FILE)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.state = {
            "status": "PARK_PARTIAL", "project": "mq",
            "namespace": "mayabank-mq-local",
            "workloads": [{"kind": "deployment", "name": "mq", "replicas": 1}],
            "apps": [{"namespace": "openshift-gitops", "name": "mayabank-mq-local-core",
                      "automated": {"selfHeal": True}}],
            "cronjobs": [], "pvc": [],
        }

    def test_finalize_no_cluster_mutation_when_fully_stopped(self):
        written = []
        def fake_get(ns, kind, name):
            if kind == "application":
                return {"spec": {"syncPolicy": {}}}
            return {"spec": {"replicas": 0}, "status": {"readyReplicas": 0}}
        with patch.object(self.mod, "original", return_value=self.state):
            with patch.object(self.mod, "verify"):
                with patch.object(self.mod.m, "get", side_effect=fake_get):
                    with patch.object(self.mod, "running_pods", return_value=[]):
                        with patch.object(self.mod, "snap", side_effect=lambda st: written.append(dict(st))):
                            self.mod.finalize("mq")
        self.assertEqual(written[0]["status"], "PARKED")

    def test_finalize_blocks_still_running(self):
        with patch.object(self.mod, "original", return_value=self.state):
            with patch.object(self.mod, "verify"):
                with patch.object(self.mod.m, "get", return_value={"spec": {"replicas": 0}}):
                    with patch.object(self.mod, "running_pods", return_value=["terminating-pod"]):
                        with patch.object(self.mod, "snap") as save:
                            with self.assertRaisesRegex(RuntimeError, "RUNNING_PODS_REMAIN"):
                                self.mod.finalize("mq")
                            save.assert_not_called()

if __name__ == "__main__":
    unittest.main()

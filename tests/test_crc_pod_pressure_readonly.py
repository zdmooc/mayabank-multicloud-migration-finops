"""Offline synthetic test: CRC pod slots differ from historical pod objects."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "crc_pressure", ROOT / "scripts" / "audit-crc-pod-pressure-readonly.py"
)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


def pod(name, namespace, phase, node="crc", build=False, emptydir=False):
    mounts = [{"name": "data", "mountPath": "/var/lib/postgresql/data"}] if emptydir else []
    spec = {
        "nodeName": node,
        "containers": [{"name": "postgres", "volumeMounts": mounts}],
        "volumes": [{"name": "data", "emptyDir": {}}] if emptydir else [],
    }
    return {
        "metadata": {
            "name": name,
            "namespace": namespace,
            "ownerReferences": [{"kind": "Build"}] if build else [],
        },
        "spec": spec,
        "status": {"phase": phase},
    }


class PressureTest(unittest.TestCase):
    def test_terminal_builds_do_not_consume_assigned_nonterminal_slot(self):
        source = {
            "items": [
                pod("api-gateway-1-build", "wero-poc", "Succeeded", build=True),
                pod("api-gateway-2-build", "wero-poc", "Failed", build=True),
                pod("postgres-0", "tradeops", "Running", emptydir=True),
                pod("app-1", "instant-payments-local", "Running"),
                pod("app-2", "instant-payments-local", "Pending"),
                pod("unassigned", "tradeops", "Pending", node=""),
            ]
        }
        nodes = {"items": [{"metadata": {"name": "crc"}, "status": {
            "capacity": {"pods": "269"}, "allocatable": {"pods": "269"}
        }}]}
        report = module.count_pods(source, nodes)
        self.assertEqual(report["all_pod_objects"], 6)
        self.assertEqual(report["all_nonterminal_pod_objects"], 4)
        self.assertEqual(report["nodes"][0]["assigned"], 3)
        self.assertEqual(report["nodes"][0]["remaining"], 266)
        self.assertEqual(report["historical_builds"]["wero-poc"]["build_terminal"], 2)
        byname = {x["namespace"]: x for x in report["namespace_rows"]}
        self.assertEqual(byname["wero-poc"]["assigned_nonterminal"], 0)
        self.assertEqual(byname["tradeops"]["assigned_nonterminal"], 1)
        self.assertTrue(byname["instant-payments-local"]["protected"])
        self.assertEqual(report["tradeops_ephemeral_mounts"],
                         [("postgres-0", "postgres", "/var/lib/postgresql/data", "Running")])

    def test_build_name_alone_detected(self):
        report = module.count_pods(
            {"items": [pod("payment-service-17-build", "wero-poc", "Succeeded")]},
            {"items": []},
        )
        self.assertEqual(report["historical_builds"]["wero-poc"]["build_total"], 1)


if __name__ == "__main__":
    unittest.main()

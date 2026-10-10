"""Offline-only bounded CRC application PARK/RESUME contract tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "crc-application-mode.py"
spec = importlib.util.spec_from_file_location("crc_app_mode", SOURCE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def deployment(name, image, volumes=None):
    return {
        "metadata": {"name": name, "uid": "uid-" + name},
        "spec": {
            "replicas": 1,
            "template": {"spec": {
                "containers": [{"name": "app", "image": image}],
                "volumes": volumes or [],
            }},
        },
    }


class ParkSafetyTests(unittest.TestCase):
    def test_rejects_emptydir_pvc_and_database(self):
        self.assertEqual(mod.is_stateless(deployment("pg", "postgres:16"))[1],
                         "STATEFUL_CONTAINER_IMAGE")
        self.assertEqual(mod.is_stateless(deployment(
            "api", "demo:1", [{"name": "cache", "emptyDir": {}}]))[1],
            "DATA_OR_EPHEMERAL_VOLUME")
        self.assertEqual(mod.is_stateless(deployment(
            "api", "demo:1", [{"name": "db", "persistentVolumeClaim": {"claimName": "x"}}]))[1],
            "DATA_OR_EPHEMERAL_VOLUME")
        self.assertTrue(mod.is_stateless(deployment("api", "demo:v1"))[0])

    def test_only_expected_stateless_targets_and_gitops(self):
        def items(resource, ns):
            if resource == "deployments":
                result = [deployment(name, "example.com/app:v1") for name in mod.TARGETS]
                result[1]["spec"]["template"]["spec"]["volumes"] = [
                    {"name": "data", "emptyDir": {}}
                ]
                return result
            if resource == "hpa":
                return [{"spec": {"scaleTargetRef": {
                    "kind": "Deployment", "name": mod.TARGETS[2]
                }}}]
            if resource == "applications.argoproj.io":
                return [{"metadata": {"name": "instant-payments-local", "uid": "appuid"},
                         "spec": {"destination": {"namespace": mod.NS},
                                  "syncPolicy": {"automated": {"selfHeal": True}}}}]
            raise AssertionError((resource, ns))
        with patch.object(mod, "oc", return_value={
            "items": [{"metadata": {"name": "crc"}, "status": {
                "conditions": [{"type": "Ready", "status": "True"}]}}]
        }), patch.object(mod, "items", side_effect=items):
            selected, apps, blocked = mod.inspect()
        self.assertEqual(len(selected), len(mod.TARGETS) - 2)
        self.assertEqual(len(apps), 1)
        self.assertIn("reconciliation-service:DATA_OR_EPHEMERAL_VOLUME", blocked)
        self.assertIn("acceptor-service:HPA_CONTROLLED", blocked)
        self.assertNotIn("postgres", ",".join(x["name"] for x in selected))

    def test_park_and_resume_snapshot_and_changes(self):
        with TemporaryDirectory() as td:
            original_state = mod.STATE
            mod.STATE = Path(td) / "state.json"
            selected = [
                {"name": "payment-orchestrator", "replicas": 1, "uid": "uid-a"},
                {"name": "consumer-psp", "replicas": 1, "uid": "uid-b"},
            ]
            apps = [{"name": "instant-payments-local",
                     "automated": {"selfHeal": True}, "uid": "appuid"}]
            events = []
            try:
                with patch.dict(os.environ, {"CRC_CAPACITY_PARK": "YES"}), \
                     patch.object(mod, "inspect", return_value=(
                         selected, apps, ["demo-cockpit:DATA_OR_EPHEMERAL_VOLUME"])), \
                     patch.object(mod, "pause_gitops", side_effect=lambda n: events.append("pause:" + n)), \
                     patch.object(mod, "scale", side_effect=lambda n, x: events.append(f"scale:{n}:{x}")):
                    mod.park()
                self.assertEqual(mod.load_state()["status"], "PARKED")
                self.assertEqual(events, [
                    "pause:instant-payments-local",
                    "scale:payment-orchestrator:0",
                    "scale:consumer-psp:0",
                ])
                with patch.dict(os.environ, {"CRC_CAPACITY_RESUME": "YES"}), \
                     patch.object(mod, "oc", side_effect=lambda *args, **kw: {
                         "metadata": {"uid": "uid-a" if "payment-orchestrator" in args else "uid-b"}
                     }), \
                     patch.object(mod, "scale", side_effect=lambda n, x: events.append(f"scale:{n}:{x}")), \
                     patch.object(mod, "app_automated", return_value=None), \
                     patch.object(mod, "restore_gitops", side_effect=lambda n, a: events.append("restore:" + n)):
                    mod.resume()
                self.assertEqual(mod.load_state()["status"], "RESUMED")
                self.assertEqual(events[-3:], [
                    "scale:payment-orchestrator:1",
                    "scale:consumer-psp:1",
                    "restore:instant-payments-local",
                ])
            finally:
                mod.STATE = original_state

    def test_park_needs_explicit_permission(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "REQUIRES"):
                mod.park()


if __name__ == "__main__":
    unittest.main()

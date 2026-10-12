"""Offline only — Maya Freelance park safety and reversible snapshot tests."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "crc-maya-freelance-mode.py"
spec = importlib.util.spec_from_file_location("maya_mode", SOURCE)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def deployment(name, image="example.com/service:v1", volumes=None):
    return {
        "metadata": {"name": name, "uid": "uid-" + name},
        "spec": {"replicas": 1, "template": {"spec": {
            "containers": [{"name": name, "image": image,
                            "env": ([{"name": "N8N_ENCRYPTION_KEY",
                                     "valueFrom": {"secretKeyRef": {"name": "maya-freelance-secrets",
                                                                     "key": "N8N_ENCRYPTION_KEY"}}}]
                                    if name == "n8n" else [])}],
            "volumes": volumes or [],
        }}},
    }


class MayaSafety(unittest.TestCase):
    def test_never_classifies_database_or_persistent_volume_as_stateless(self):
        self.assertFalse(mod.stateless_deployment(deployment("postgres", "postgres:16")))
        self.assertFalse(mod.stateless_deployment(deployment(
            "n8n", volumes=[{"name": "data", "persistentVolumeClaim": {"claimName": "postgres-data"}}])))
        self.assertFalse(mod.stateless_deployment(deployment(
            "n8n", volumes=[{"name": "data", "emptyDir": {}}])))
        self.assertTrue(mod.stateless_deployment(deployment("n8n")))

    def test_preflight_confirms_pvc_and_only_two_deployments(self):
        ds = [deployment("n8n"), deployment("maya-dashboard"),
              deployment("postgres", "quay.io/postgresql:16",
                         [{"name": "data", "persistentVolumeClaim": {"claimName": "postgres-data"}}])]
        def list_items(resource, namespace):
            if resource == "deployments":
                return ds
            if resource in ("hpa", "applications.argoproj.io"):
                return []
            raise AssertionError(resource)
        def oc(*args, **kwargs):
            if args[0] == "get" and args[1] == "nodes":
                return {"items": [{"metadata": {"name": "crc"}, "status": {
                    "conditions": [{"type": "Ready", "status": "True"}]}}]}
            if args[0:4] == ("-n", mod.NAMESPACE, "get", "pvc"):
                return {"status": {"phase": "Bound"}}
            raise AssertionError(args)
        with patch.object(mod, "oc", side_effect=oc):
            with patch.object(mod, "list_items", side_effect=list_items):
                selected, apps = mod.preflight()
        self.assertEqual({s["name"] for s in selected}, {"n8n", "maya-dashboard"})
        self.assertEqual(apps, [])

    def test_park_needs_consent_and_restores_replicas(self):
        ds = [{"name": n, "replicas": 1, "uid": "uid-" + n} for n in mod.TARGETS]
        apps = [{"name": "maya", "automated": {"prune": True}, "uid": "argo"}]
        with TemporaryDirectory() as tmp:
            previous = mod.STATE
            mod.STATE = Path(tmp) / "state.json"
            events = []
            try:
                with patch.dict(os.environ, {"CRC_MAYA_PARK": "YES"}, clear=True):
                    with self.assertRaisesRegex(RuntimeError, "FOUR_ACKNOWLEDGEMENTS"):
                        mod.park()
                with patch.object(mod, "preflight", return_value=(ds, apps)):
                    with patch.object(mod, "change_auto", side_effect=lambda *a: events.append(("argo", a))):
                        with patch.object(mod, "scale", side_effect=lambda *a: events.append(("scale", a))):
                            with patch.dict(os.environ, {
                                "CRC_MAYA_PARK": "YES",
                                "CRC_MAYA_ACK_N8N_DOWNTIME": "YES",
                                "CRC_MAYA_ACK_EPHEMERAL_HOME_LOSS": "YES",
                                "CRC_MAYA_ACK_WORKFLOWS_QUIESCED": "YES"}, clear=True):
                                mod.park()
                self.assertEqual(mod.read_state()["status"], "PARKED")
                self.assertEqual(len([e for e in events if e[0] == "scale"]), 2)
                self.assertEqual(events[0], ("argo", ("maya", None)))
                with patch.object(mod, "oc", side_effect=lambda *args, **kwargs: {
                        "metadata": {"uid": "uid-" + args[3]}}):
                    with patch.object(mod, "app_auto", return_value=None):
                        with patch.object(mod, "change_auto", side_effect=lambda *a: events.append(("argo", a))):
                            with patch.object(mod, "scale", side_effect=lambda *a: events.append(("scale", a))):
                                with patch.dict(os.environ, {"CRC_MAYA_RESUME": "YES"}, clear=True):
                                    mod.resume()
                self.assertEqual(mod.read_state()["status"], "RESUMED")
                self.assertEqual(events[-1], ("argo", ("maya", {"prune": True})))
            finally:
                mod.STATE = previous


if __name__ == "__main__":
    unittest.main()

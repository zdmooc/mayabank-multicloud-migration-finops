"""Offline contract tests for reversible CRC trading/decision/API parking."""
import importlib.util
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "crc-extra-projects-mode.py"
spec = importlib.util.spec_from_file_location("crc_extra_mode", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def state(project):
    namespace = mod.PROJECTS[project]["namespace"]
    deployments = [{"name": x, "uid": "uid-" + x, "replicas": 1}
                   for x in mod.PROJECTS[project]["deployments"]]
    apps = ([{"name": "mayainsurance-decision", "uid": "argo-uid",
              "automated": {"selfHeal": True}}] if project == "decision" else [])
    cronjobs = ([{"name": "morning", "uid": "cron-uid", "suspend": False}] if project == "trading" else [])
    return {"project": project, "namespace": namespace,
            "deployments": deployments, "applications": apps, "cronjobs": cronjobs}


class ExtraProjectModeTests(unittest.TestCase):
    def test_park_requires_two_acknowledgements(self):
        with patch.dict(os.environ, {"CRC_EXTRA_PARK": "YES"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "EXPLICIT_ACKS"):
                mod.park("api")

    def test_decision_pauses_gitops_then_parks_and_snapshots(self):
        with TemporaryDirectory() as td:
            with patch.object(mod, "ROOT", Path(td)):
                with patch.dict(os.environ, {"CRC_EXTRA_PARK": "YES", "CRC_EXTRA_ACK_DOWNTIME": "YES"}):
                    events = []
                    with patch.object(mod, "inspect", return_value=state("decision")):
                        with patch.object(mod, "patch_app", side_effect=lambda *x: events.append(("argocd", *x))):
                            with patch.object(mod, "scale", side_effect=lambda *x: events.append(("scale", *x))):
                                mod.park("decision")
                    self.assertEqual(events[0], ("argocd", "mayainsurance-decision", None))
                    self.assertEqual(events[1], ("scale", "mayainsurance-decision-local", "decision-api", 0))
                    self.assertEqual(mod.state_read(mod.snapshot_path("decision"))["status"], "PARKED")
                    with self.assertRaisesRegex(RuntimeError, "EXISTING_ACTIVE_SNAPSHOT"):
                        mod.park("decision")

    def test_trading_suspends_cronjobs_before_scaling(self):
        with TemporaryDirectory() as td:
            with patch.object(mod, "ROOT", Path(td)):
                with patch.dict(os.environ, {"CRC_EXTRA_PARK": "YES", "CRC_EXTRA_ACK_DOWNTIME": "YES"}):
                    events = []
                    with patch.object(mod, "inspect", return_value=state("trading")):
                        with patch.object(mod, "patch_cj", side_effect=lambda *x: events.append(("cronjob", *x))):
                            with patch.object(mod, "scale", side_effect=lambda *x: events.append(("scale", *x))):
                                mod.park("trading")
                    self.assertEqual(events[0], ("cronjob", "trading-perso", "morning", True))
                    self.assertEqual(events[1], ("scale", "trading-perso", "rapport-horaire", 0))

    def test_resume_restores_saved_counts_and_argo(self):
        with TemporaryDirectory() as td:
            with patch.object(mod, "ROOT", Path(td)):
                snapshot = state("decision")
                snapshot["status"] = "PARKED"
                mod.state_write(mod.snapshot_path("decision"), snapshot)
                events = []
                def fake_get(ns, kind, name):
                    if kind == "deployment":
                        return {"metadata": {"uid": "uid-" + name}}
                    if kind == "application":
                        return {"metadata": {"uid": "argo-uid"}, "spec": {"syncPolicy": {}}}
                    raise AssertionError(kind)
                with patch.object(mod, "check_crc"):
                    with patch.object(mod, "get", side_effect=fake_get):
                        with patch.object(mod, "scale", side_effect=lambda *x: events.append(("scale", *x))):
                            with patch.object(mod, "patch_app", side_effect=lambda *x: events.append(("argocd", *x))):
                                with patch.dict(os.environ, {"CRC_EXTRA_RESUME": "YES"}):
                                    mod.resume("decision")
                self.assertEqual(events, [
                    ("scale", "mayainsurance-decision-local", "decision-api", 1),
                    ("argocd", "mayainsurance-decision", {"selfHeal": True})])
                self.assertEqual(mod.state_read(mod.snapshot_path("decision"))["status"], "RESUMED")

    def test_rejects_data_volumes_and_unexpected_deployments(self):
        def make_item(name, vols):
            return {"metadata": {"name": name, "uid": "u"}, "spec": {
                "replicas": 1, "template": {"spec": {"containers": [{"image": "safe:v1"}], "volumes": vols}}}}
        def fake_ls(ns, kind):
            if kind == "deployments":
                return [make_item("rapport-horaire", [{"name": "db",
                         "persistentVolumeClaim": {"claimName": "data"}}])]
            return []
        with patch.object(mod, "check_crc"):
            with patch.object(mod, "ls", side_effect=fake_ls):
                with self.assertRaisesRegex(RuntimeError, "UNSAFE_VOLUME"):
                    mod.inspect("trading")


if __name__ == "__main__":
    unittest.main()

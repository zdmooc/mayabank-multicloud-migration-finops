"""Offline unit tests: CRC is never contacted."""
import importlib.util
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "crc-idle-services-mode.py"
spec = importlib.util.spec_from_file_location("crc_idle_services", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CrcIdleTests(unittest.TestCase):
    def test_parks_require_explicit_acks(self):
        with patch.dict(os.environ, {}, clear=True):
            for p in ("instant", "keycloak"):
                with self.assertRaisesRegex(RuntimeError, "ACK"):
                    m.park(p)

    def test_plan_keycloak_read_only(self):
        sample = {"project":"keycloak", "ns":"keycloak-system",
                  "cr":{"instances":1}, "workloads":[{"kind":"statefulset",
                  "name":"postgresql", "replicas":1}], "pvc":[{"name":"postgres-pvc"}]}
        with TemporaryDirectory() as td:
            with patch.object(m, "ROOT", Path(td)),patch.object(m, "inspect", return_value=sample):
                with patch.object(m, "scale") as scale, patch.object(m, "patch") as patcher:
                    m.plan("keycloak")
                    scale.assert_not_called()
                    patcher.assert_not_called()

    def test_keycloak_reconcile_before_database_shutdown(self):
        actions=[]
        sample={"project":"keycloak","ns":"keycloak-system",
                "cr":{"instances":1},"workloads":[{"kind":"statefulset",
                "name":"postgresql","replicas":1}],"pvc":[]}
        with TemporaryDirectory() as td:
            with patch.object(m,"ROOT",Path(td)),patch.object(m,"inspect",return_value=sample):
                with patch.object(m,"kc_instances",side_effect=lambda n:actions.append(("keycloak",n))):
                    with patch.object(m,"scale",side_effect=lambda *args:actions.append(("postgres",args[-1]))):
                        with patch.object(m,"wait"):
                            with patch.dict(os.environ,{
                                "CRC_IDLE_PARK":"YES",
                                "CRC_IDLE_ACK_DOWNTIME":"YES",
                                "CRC_IDLE_ACK_LAB_DATA_LOSS":"YES"
                            }, clear=True):
                                m.park("keycloak")
        self.assertEqual(actions,[("keycloak",0),("postgres",0)])

    def test_instant_stops_datastore_after_observability(self):
        actions=[]
        names=list(m.REST)
        sample={"project":"instant","ns":"instant-payments-local",
                "workloads":[{"kind":"deployment","name":n,"replicas":1} for n in names]
                +[{"kind":"statefulset","name":"mongodb-read-model","replicas":1}],
                "pvc":[],"cron":[]}
        with TemporaryDirectory() as td:
            with patch.object(m,"ROOT",Path(td)),patch.object(m,"inspect",return_value=sample):
                with patch.object(m,"scale",side_effect=lambda *a:actions.append(a[2])):
                    with patch.object(m,"wait"):
                        with patch.dict(os.environ,{
                            "CRC_IDLE_PARK":"YES",
                            "CRC_IDLE_ACK_DOWNTIME":"YES",
                            "CRC_IDLE_ACK_LAB_DATA_LOSS":"YES"
                        }, clear=True):
                            m.park("instant")
        self.assertEqual(actions, names+["mongodb-read-model"])

    def test_snapshot_refuses_repeat_park(self):
        with TemporaryDirectory() as td:
            with patch.object(m,"ROOT",Path(td)):
                m.store({"project":"instant","ns":"instant-payments-local","status":"PARKED"})
                with patch.dict(os.environ,{
                    "CRC_IDLE_PARK":"YES",
                    "CRC_IDLE_ACK_DOWNTIME":"YES",
                    "CRC_IDLE_ACK_LAB_DATA_LOSS":"YES"}, clear=True):
                    with self.assertRaisesRegex(RuntimeError,"ACTIVE_SNAPSHOT_EXISTS"):
                        m.park("instant")

if __name__=="__main__":
    unittest.main()

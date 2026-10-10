#!/usr/bin/env python3
"""Offline synthetic contract tests. Never connects to CRC."""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-crc-postgresql-readonly.py"
spec = importlib.util.spec_from_file_location("pg_audit_readonly", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

def obj(ns, name, kind, spec=None, status=None, **more):
    return {"kind": kind, "metadata": {"namespace": ns, "name": name, **more},
            "spec": spec or {}, "status": status or {}}

class PostgreSQLReadOnlyTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(audit.to_cpu("250m"), 250)
        self.assertEqual(audit.to_cpu("0.2"), 200)
        self.assertEqual(audit.to_mi("1Gi"), 1024)
        self.assertEqual(audit.to_mi("512Mi"), 512)

    def test_redaction_and_hosts(self):
        self.assertIsNone(audit.safe_host({"name": "DATABASE_PASSWORD", "value": "do-not-show"}))
        self.assertIsNone(audit.safe_host({"name": "POSTGRES_HOST", "valueFrom": {"secretKeyRef": {"name": "s", "key": "host"}}}))
        self.assertEqual(audit.safe_host({"name": "POSTGRES_HOST", "value": "postgres"}), "postgres")
        self.assertEqual(audit.safe_host({"name": "KC_DB_URL", "value": "jdbc:postgresql://operator:private@db.example:5432/test"}), "db.example")

    def test_report_is_private_and_no_secrets(self):
        server = obj("tradeops", "postgres", "StatefulSet", {
            "replicas": 1,
            "template": {"metadata": {"labels": {"app": "postgres"}},
                         "spec": {"containers": [{"name": "db", "image": "postgres:16"}]}}
        }, {"readyReplicas": 1})
        app = obj("tradeops", "api", "Deployment", {
            "replicas": 1,
            "template": {"metadata": {"labels": {"app": "api"}}, "spec": {
                "containers": [{"name": "app", "image": "alpine:latest",
                                "env": [{"name": "POSTGRES_HOST", "value": "postgres"},
                                        {"name": "DATABASE_PASSWORD", "value": "ULTRA_PRIVATE_TOKEN_VALUE"}]}]}}
        })
        pod = obj("tradeops", "postgres-0", "Pod", {
            "containers": [{"name": "db", "image": "postgres:16",
                            "resources": {"requests": {"cpu": "100m", "memory": "128Mi"}}}],
            "volumes": [{"name": "pgdata", "persistentVolumeClaim": {"claimName": "pgdata"}}]
        }, {"phase": "Running"},
            ownerReferences=[{"kind": "StatefulSet", "name": "postgres"}])
        svc = obj("tradeops", "postgres", "Service", {"selector": {"app": "postgres"}})
        pvc = obj("tradeops", "pgdata", "PersistentVolumeClaim", {
            "volumeName": "pv-a", "resources": {"requests": {"storage": "1Gi"}}
        }, {"phase": "Bound"})
        pv = obj("", "pv-a", "PersistentVolume", {"persistentVolumeReclaimPolicy": "Retain"})
        items = {
            "deployments,statefulsets": [server, app],
            "pods": [pod], "replicasets": [], "services": [svc], "pvc": [pvc], "pv": [pv]
        }
        def fake_run(args, **kwargs):
            if args[:3] == ["oc", "adm", "top"]:
                return SimpleNamespace(returncode=0,
                  stdout="NAMESPACE POD NAME CPU(cores) MEMORY(bytes)\ntradeops postgres-0 db 3m 50Mi\n")
            if args[:2] == ["oc", "get"]:
                return SimpleNamespace(returncode=0,
                  stdout=json.dumps({"items": items[args[2]]}))
            raise AssertionError("unexpected command (possible mutation): " + str(args))
        old = os.getcwd()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.chdir(tmp)
                with patch.object(sys, "argv", ["audit"]), patch.object(subprocess, "run", side_effect=fake_run), contextlib.redirect_stdout(io.StringIO()) as out:
                    audit.main()
                folder = next(Path("evidence/local").iterdir())
                summary = (folder / "SUMMARY.txt").read_text()
                db_csv = (folder / "postgresql-workloads.csv").read_text()
                links_csv = (folder / "database-consumer-candidates.csv").read_text()
                self.assertIn("WORKLOAD_COUNT=1", summary)
                self.assertIn("READY_REPLICAS=1", summary)
                self.assertIn("TOP_MATCHED_PG_CONTAINERS=1", summary)
                self.assertIn("SVC_SELECTOR_CANDIDATE_NOT_PROVEN_SQL", links_csv)
                self.assertIn("postgres:16", db_csv)
                self.assertIn("pgdata:Bound:1Gi:Retain:pv-a", db_csv)
                self.assertIn("100.0", db_csv)
                self.assertIn("50.0", db_csv)
                self.assertNotIn("ULTRA_PRIVATE_TOKEN_VALUE", summary+db_csv+links_csv+out.getvalue())
        finally:
            os.chdir(old)

if __name__ == "__main__":
    unittest.main()

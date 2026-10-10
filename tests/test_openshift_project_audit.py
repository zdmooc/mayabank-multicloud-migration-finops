#!/usr/bin/env python3
"""Offline synthetic tests for the universal CRC project audit. No Kubernetes connection."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("project_crc_audit", ROOT / "scripts/audit-openshift-project-readonly.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)

def obj(name, kind, ns="tradeops", spec=None, status=None, **meta):
    return {"metadata": {"name": name, "namespace": ns, **meta}, "kind": kind,
            "spec": spec or {}, "status": status or {}}

class ProjectAuditContracts(unittest.TestCase):
    def test_units_and_top(self):
        self.assertEqual(audit.to_cpu("25m"), 25)
        self.assertEqual(audit.to_mem("1Gi"), 1024)
        text = "POD NAME CPU(cores) MEMORY(bytes)\npostgres-0 pg 10m 35Mi\n"
        self.assertEqual(audit.parse_top(text, "tradeops")[("tradeops", "postgres-0", "pg")], [10, 35])

    def test_secret_safe_hostname_extraction(self):
        self.assertEqual(audit.safe_host_env({"name": "POSTGRES_HOST", "value": "postgres"}), "postgres")
        self.assertIsNone(audit.safe_host_env({"name": "DATABASE_PASSWORD", "value": "SECRET_VALUE"}))
        self.assertIsNone(audit.safe_host_env({"name": "POSTGRES_HOST", "value": "user:pass@db"}))

    def test_tradeops_emptydir_and_no_secret_leak(self):
        server = obj("postgres", "StatefulSet", spec={
            "replicas": 1,
            "template": {"metadata": {"labels": {"app": "postgres"}},
                         "spec": {"containers": [{"name": "pg", "image": "postgres:16",
                          "resources": {"requests": {"cpu": "25m", "memory": "128Mi"}},
                          "volumeMounts": [{"name": "data", "mountPath": "/var/lib/postgresql/data"}]}],
                          "volumes": [{"name": "data", "emptyDir": {}}]}}}, status={"readyReplicas": 1})
        api = obj("api", "Deployment", spec={"replicas": 1, "template": {
            "metadata": {"labels": {"app": "api"}},
            "spec": {"containers": [{"name": "app", "image": "example:latest", "env": [
                {"name": "POSTGRES_HOST", "value": "postgres"},
                {"name": "POSTGRES_PASSWORD", "value": "SECRET_SHOULD_NEVER_LEAVE_MEMORY"}]}]}}}, status={"readyReplicas": 1})
        pod = obj("postgres-0", "Pod", spec={"containers": [{
            "name": "pg", "image": "postgres:16",
            "resources": {"requests": {"cpu": "25m", "memory": "128Mi"}},
            "volumeMounts": [{"name": "data", "mountPath": "/var/lib/postgresql/data"}]}],
            "volumes": [{"name": "data", "emptyDir": {}}]}, status={"phase": "Running"},
            ownerReferences=[{"kind": "StatefulSet", "name": "postgres"}])
        svc = obj("postgres", "Service", spec={"selector": {"app": "postgres"}})
        contents = {"statefulsets": [server], "deployments": [api], "pods": [pod], "services": [svc]}
        def fake_get(ns, resource, name=None):
            if resource == "namespace":
                return obj("tradeops", "Namespace")
            return {"items": contents.get(resource, [])}
        with patch.object(audit, "get_obj", side_effect=fake_get), patch.object(
                audit, "run", return_value=(True, "POD NAME CPU(cores) MEMORY(bytes)\npostgres-0 pg 10m 35Mi\n")):
            data = audit.analyze_namespace("tradeops", include_gitops=False)
        codes = [f["code"] for f in data["findings"]]
        self.assertIn("EPHEMERAL_STATEFUL_DATA", codes)
        self.assertEqual(data["sample"]["top_container_match"], "1/1")
        self.assertEqual(data["sample"]["ram_top_mi_matched_only"], 35)
        self.assertEqual(len(data["db_consumer_candidates"]), 1)
        text = json.dumps(data) + audit.markdown(data)
        self.assertNotIn("SECRET_SHOULD_NEVER_LEAVE_MEMORY", text)

if __name__ == "__main__":
    unittest.main()

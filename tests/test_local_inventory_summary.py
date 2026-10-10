#!/usr/bin/env python3
"""Offline tests with synthetic Kubernetes CSVs, no cluster or credentials."""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_csv(root, filename, headings, rows):
    with (root / filename).open("w", newline="", encoding="utf-8") as f:
        out = csv.writer(f)
        out.writerow(headings)
        out.writerows(rows)


class NumericInventorySummaryTests(unittest.TestCase):
    def test_pressure_and_grouping_are_sanitized(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            write_csv(root, "pod-resources.csv",
                ["namespace", "pod", "phase", "container", "cpu_request", "memory_request", "cpu_limit", "memory_limit"],
                [
                    ["openshift-testing", "internal-canary", "Running", "app", "500m", "512Mi", "1", "1Gi"],
                    ["demo-workload", "pending-pod", "Pending", "app", "100m", "128Mi", "500m", "256Mi"],
                    ["demo-workload", "finished-pod", "Succeeded", "app", "1000m", "2Gi", "2", "4Gi"],
                ])
            write_csv(root, "node-allocatable.csv",
                ["node", "allocatable_cpu", "allocatable_memory", "capacity_cpu", "capacity_memory"],
                [["synthetic-node", "2", "4096Mi", "2", "4096Mi"]])
            write_csv(root, "pvc-requests.csv",
                ["namespace", "pvc", "phase", "storage_class", "requested_storage"],
                [["demo-workload", "db", "Bound", "test", "5Gi"]])
            proc = subprocess.run(
                [sys.executable, str(ROOT / "scripts/summarize-local-inventory.py"), str(root)],
                capture_output=True, text=True, check=True
            )
            data = dict(line.split("=", 1) for line in proc.stdout.splitlines() if "=" in line)
            self.assertEqual(data["pod_count"], "3")
            self.assertEqual(data["active_running_pending_container_count"], "2")
            self.assertEqual(data["running_requests_cpu_m"], "500.00")
            self.assertEqual(data["active_requests_cpu_m"], "600.00")
            self.assertEqual(data["active_requests_cpu_pct_allocatable"], "30.00")
            self.assertEqual(data["running_requests_cpu_pct_allocatable"], "25.00")
            self.assertEqual(data["active_requests_memory_pct_allocatable"], "15.62")
            self.assertEqual(data["pending_container_cpu_request_m"], "100.00")
            self.assertEqual(data["pending_container_memory_request_mi"], "128.00")
            self.assertEqual(data["openshift_prefix_active_requests_cpu_m"], "500.00")
            self.assertEqual(data["other_namespace_prefix_active_requests_cpu_m"], "100.00")
            self.assertEqual(data["pvc_requested_gib"], "5.00")
            self.assertNotIn("internal-canary", proc.stdout)
            self.assertNotIn("synthetic-node", proc.stdout)
            self.assertNotIn("demo-workload", proc.stdout)


if __name__ == "__main__":
    unittest.main()

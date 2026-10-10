#!/usr/bin/env python3
"""Synthetic only, verifies grouped metrics matching without printing identifiers."""
import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Coverage(unittest.TestCase):
    def test_match_missing_extra_and_safety(self):
        with tempfile.TemporaryDirectory() as scratch:
            directory = Path(scratch)
            with (directory / "pod-resources.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["namespace", "pod", "phase", "container", "cpu_request", "memory_request", "cpu_limit", "memory_limit"])
                w.writerow(["instant-payments-local", "sensitive-payment-pod", "Running", "processor", "100m", "128Mi", "200m", "256Mi"])
                w.writerow(["instant-payments-local", "missing-metric", "Running", "worker", "200m", "256Mi", "500m", "512Mi"])
                w.writerow(["openshift-test", "finished", "Succeeded", "old-container", "500m", "1Gi", "", ""])
            (directory / "top-pods-now.txt").write_text(
                "NAMESPACE POD NAME CPU(cores) MEMORY(bytes)\n"
                "instant-payments-local sensitive-payment-pod processor 7m 75Mi\n"
                "openshift-test extra-but-unscheduled agent 3m 10Mi\n",
                encoding="utf-8",
            )
            run = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check-local-top-coverage.py"), str(directory)],
                text=True, capture_output=True, check=True
            )
            self.assertIn("running_container_rows=2", run.stdout)
            self.assertIn("top_container_rows=2", run.stdout)
            self.assertIn("matched_container_rows=1", run.stdout)
            self.assertIn("running_inventory_metric_coverage_pct=50.00", run.stdout)
            self.assertIn("matched_requested_cpu_m=100.00", run.stdout)
            self.assertIn("matched_observed_cpu_m=7.00", run.stdout)
            self.assertIn("matched_requested_memory_mi=128.00", run.stdout)
            self.assertIn("matched_observed_memory_mi=75.00", run.stdout)
            self.assertIn("matched_cpu_observed_pct_request=7.00", run.stdout)
            self.assertIn("matched_memory_observed_pct_request=58.59", run.stdout)
            self.assertIn("unmatched_requested_cpu_m=200.00", run.stdout)
            self.assertIn("unmatched_requested_memory_mi=256.00", run.stdout)
            self.assertIn("missing_top_for_running_rows=1", run.stdout)
            self.assertIn("top_rows_not_in_running_requests=1", run.stdout)
            self.assertIn("group_payments_matched_requested_cpu_m=100.00", run.stdout)
            self.assertIn("group_payments_matched_used_cpu_m=7.00", run.stdout)
            self.assertIn("group_payments_matched_used_memory_mi=75.00", run.stdout)
            self.assertIn("NO_IDENTIFIERS_PRINTED=true", run.stdout)
            for confidential in ("sensitive-payment-pod", "missing-metric", "extra-but-unscheduled",
                                 "processor", "worker", "instant-payments-local"):
                self.assertNotIn(confidential, run.stdout)

    def test_non_container_top_is_rejected_without_names(self):
        with tempfile.TemporaryDirectory() as scratch:
            directory = Path(scratch)
            with (directory / "pod-resources.csv").open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["namespace", "pod", "phase", "container", "cpu_request", "memory_request", "cpu_limit", "memory_limit"])
                w.writerow(["test-namespace", "a-pod", "Running", "a-container", "100m", "64Mi", "", ""])
            (directory / "top-pods-now.txt").write_text(
                "NAMESPACE NAME CPU(cores) MEMORY(bytes)\n"
                "test-namespace a-pod 10m 55Mi\n", encoding="utf-8"
            )
            p = subprocess.run(
                [sys.executable, str(ROOT / "scripts/check-local-top-coverage.py"), str(directory)],
                text=True, capture_output=True
            )
            self.assertNotEqual(p.returncode, 0)
            self.assertNotIn("test-namespace", p.stderr)


if __name__ == "__main__":
    unittest.main()

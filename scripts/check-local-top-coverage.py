#!/usr/bin/env python3
"""Offline compare Running container request identities to a single oc adm top container sample.

Only prints grouped numbers. Never prints namespace, pod, node, container or token values.
Does not modify Kubernetes and requires only Python standard library.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path


def cpu_m(value):
    s = (value or "").strip()
    if not s:
        return 0.0
    for unit, factor in (("m", 1), ("u", .001), ("n", .000001)):
        if s.endswith(unit):
            return float(s[:-len(unit)]) * factor
    return float(s) * 1000


def mem_mi(value):
    s = (value or "").strip()
    if not s:
        return 0.0
    for unit, factor in (
        ("Ki", 1/1024), ("Mi", 1), ("Gi", 1024),
        ("Ti", 1024*1024), ("K", 1000/(1024*1024)),
        ("M", 1000000/(1024*1024)), ("G", 1000000000/(1024*1024))
    ):
        if s.endswith(unit):
            return float(s[:-len(unit)]) * factor
    return float(s)/(1024*1024)


GROUPS = {
    "instant-payments-local": "payments",
    "tradeops": "tradeops_partial",
    "maya-freelance": "freelance",
    "mayainsurance-decision-local": "decision",
    "mayabank-mq-local": "ibm_mq",
    "keycloak-system": "identity",
    "mayabank-api": "api_mixed",
    "shared-observability": "shared_otel",
    "shared-platform-services": "platform_operator",
    "hostpath-provisioner": "local_storage",
}


def group(namespace):
    return "openshift_prefix" if namespace.startswith("openshift-") else GROUPS.get(namespace, "unclassified_other")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    root = args.directory
    try:
        with (root / "pod-resources.csv").open(newline="", encoding="utf-8-sig") as f:
            requested_rows = list(csv.DictReader(f))
        source = {}
        for row in requested_rows:
            if row["phase"] != "Running":
                continue
            key = (row["namespace"], row["pod"], row["container"])
            if key in source:
                raise ValueError("Duplicate container identity in source CSV")
            source[key] = (
                cpu_m(row["cpu_request"]),
                mem_mi(row["memory_request"]),
            )

        lines = (root / "top-pods-now.txt").read_text(encoding="utf-8-sig").splitlines()
        metrics = {}
        header_found = False
        for line in lines:
            cols = line.split()
            if not cols:
                continue
            if cols[:3] == ["NAMESPACE", "POD", "NAME"]:
                if len(cols) != 5 or cols[3:] != ["CPU(cores)", "MEMORY(bytes)"]:
                    raise ValueError("Unexpected per-container top header")
                header_found = True
                continue
            if not header_found:
                continue
            if len(cols) != 5:
                # Ignore non-tabular messages; do not print them or private values.
                continue
            try:
                cpu, mem = cpu_m(cols[3]), mem_mi(cols[4])
            except ValueError:
                continue
            key = tuple(cols[:3])
            if key in metrics:
                raise ValueError("Duplicate container identity in metrics snapshot")
            metrics[key] = (cpu, mem)
        if not header_found or not metrics or not source:
            raise ValueError("Missing source Running containers or per-container metrics snapshot")

        keys = set(source)
        observed = set(metrics)
        matched = keys & observed
        unmatched_requests = keys - observed
        unmatched_metrics = observed - keys

        print("I1_METRIC_COVERAGE=OFFLINE_IDENTITIES_CHECKED")
        print("SCOPE=single_timepoint_running_regular_containers_ONLY_NOT_P95")
        print(f"running_container_rows={len(keys)}")
        print(f"top_container_rows={len(observed)}")
        print(f"matched_container_rows={len(matched)}")
        print(f"missing_top_for_running_rows={len(unmatched_requests)}")
        print(f"top_rows_not_in_running_requests={len(unmatched_metrics)}")

        grouped = defaultdict(lambda: dict(request_rows=0, top_rows=0, matched=0,
                                           req_cpu=0., req_mem=0., used_cpu=0., used_mem=0.))
        for key in keys:
            grouped[group(key[0])]["request_rows"] += 1
        for key in observed:
            grouped[group(key[0])]["top_rows"] += 1
        for key in matched:
            row = grouped[group(key[0])]
            row["matched"] += 1
            row["req_cpu"] += source[key][0]
            row["req_mem"] += source[key][1]
            row["used_cpu"] += metrics[key][0]
            row["used_mem"] += metrics[key][1]

        for name in sorted(grouped):
            row = grouped[name]
            print(f"group_{name}_request_rows={row['request_rows']}")
            print(f"group_{name}_top_rows={row['top_rows']}")
            print(f"group_{name}_matched_rows={row['matched']}")
            print(f"group_{name}_matched_requested_cpu_m={row['req_cpu']:.2f}")
            print(f"group_{name}_matched_used_cpu_m={row['used_cpu']:.2f}")
            print(f"group_{name}_matched_requested_memory_mi={row['req_mem']:.2f}")
            print(f"group_{name}_matched_used_memory_mi={row['used_mem']:.2f}")
        print("NO_IDENTIFIERS_PRINTED=true")
        print("WARNING=matching_coverage_does_not_measure_performance_slo_or_capacity")
    except (OSError, ValueError, KeyError):
        parser.error("CSV/metrics data missing, incompatible, or contains duplicate identities; raw details remain local")


if __name__ == "__main__":
    main()

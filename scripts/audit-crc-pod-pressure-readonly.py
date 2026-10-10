#!/usr/bin/env python3
"""Read-only OpenShift/CRC pod pressure audit. No resource mutations or Secret reads.

Usage:
  python scripts/audit-crc-pod-pressure-readonly.py
  python scripts/audit-crc-pod-pressure-readonly.py --no-top

It distinguishes active node-assigned pods from terminal historical Build pods.
Dashboard pod counters may differ: this report prints its own denominators.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
import re
import subprocess
import sys

BUILD_POD = re.compile(r"^(.+)-[0-9]+-build$")
PROTECTED_NAMESPACES = {
    "instant-payments-local",
    "mayabank-mq-local",
    "tradeops",
    "maya-freelance",
    "keycloak-system",
    "openshift-gitops",
    "openshift-monitoring",
    "openshift-pipelines",
}

def run_readonly(args: list[str]) -> dict:
    proc = subprocess.run(args, capture_output=True, text=True, check=False, timeout=65)
    if proc.returncode:
        raise RuntimeError(f"{' '.join(args)} failed: {proc.stderr.strip()[:240]}")
    return json.loads(proc.stdout)

def count_pods(pods: dict, nodes: dict) -> dict:
    ns = defaultdict(lambda: Counter())
    by_node = defaultdict(lambda: Counter())
    phases = Counter()
    build_namespaces = defaultdict(lambda: Counter())
    emptydir_data = []

    for pod in pods.get("items", []):
        meta = pod.get("metadata") or {}
        spec = pod.get("spec") or {}
        status = pod.get("status") or {}
        name = meta.get("name") or "?"
        namespace = meta.get("namespace") or "?"
        phase = status.get("phase") or "Unknown"
        node_name = spec.get("nodeName") or ""
        terminal = phase in ("Succeeded", "Failed")
        active_assigned = bool(node_name) and not terminal
        owners = meta.get("ownerReferences") or []
        build = bool(BUILD_POD.match(name)) or any(
            ref.get("kind") == "Build" for ref in owners
        )

        phases[phase] += 1
        ns[namespace]["objects"] += 1
        if not terminal:
            ns[namespace]["nonterminal"] += 1
        if active_assigned:
            ns[namespace]["assigned_nonterminal"] += 1
            by_node[node_name]["assigned_nonterminal"] += 1
        if status.get("phase") == "Pending":
            ns[namespace]["pending"] += 1
        if status.get("phase") == "Running":
            ns[namespace]["running"] += 1
        if terminal:
            ns[namespace]["terminal"] += 1
        if meta.get("deletionTimestamp"):
            ns[namespace]["terminating"] += 1
        if build:
            build_namespaces[namespace]["build_total"] += 1
            build_namespaces[namespace]["build_terminal" if terminal else "build_nonterminal"] += 1

        if namespace == "tradeops":
            voltypes = {v.get("name"): v.get("emptyDir") for v in spec.get("volumes", []) if "emptyDir" in v}
            for container in spec.get("containers", []):
                for mount in container.get("volumeMounts", []):
                    mountpath = mount.get("mountPath") or ""
                    if mount.get("name") in voltypes and any(
                        token in mountpath.lower() for token in (
                            "postgres", "qdrant", "redpanda", "prometheus", "grafana"
                        )
                    ):
                        emptydir_data.append((name, container.get("name", "?"), mountpath, phase))

    node_rows = []
    for node in nodes.get("items", []):
        meta = node.get("metadata") or {}
        name = meta.get("name") or "?"
        cap = node.get("status", {}).get("capacity", {})
        alloc = node.get("status", {}).get("allocatable", {})
        maximum = int(alloc.get("pods") or cap.get("pods") or 0)
        assigned = by_node[name]["assigned_nonterminal"]
        node_rows.append({
            "name": name, "assigned": assigned, "allocatable": maximum,
            "remaining": maximum - assigned if maximum else None,
            "capacity": cap.get("pods"),
        })
    node_rows.sort(key=lambda n: n["name"])

    namespace_rows = [
        {"namespace": name, **values, "protected": name in PROTECTED_NAMESPACES or name.startswith(("openshift-", "kube-"))}
        for name, values in ns.items()
    ]
    namespace_rows.sort(key=lambda x: (-x.get("assigned_nonterminal", 0), -x["objects"], x["namespace"]))
    return {
        "phases": dict(phases),
        "all_pod_objects": sum(phases.values()),
        "all_nonterminal_pod_objects": sum(1 for p in pods.get("items", []) if (p.get("status") or {}).get("phase") not in ("Succeeded", "Failed")),
        "nodes": node_rows,
        "namespace_rows": namespace_rows,
        "historical_builds": {name: dict(counter) for name, counter in build_namespaces.items()},
        "tradeops_ephemeral_mounts": emptydir_data,
    }

def print_report(report: dict) -> None:
    print("CRC_POD_PRESSURE_AUDIT=READ_ONLY")
    print("KUBERNETES_CHANGES=false")
    print("SECRET_VALUES_ACCESSED=false")
    print("SOURCE_DELETION_AUTHORIZED=false")
    print("SOURCE_POD_OBJECTS_ALL=%d" % report["all_pod_objects"])
    print("SOURCE_POD_OBJECTS_NONTERMINAL=%d" % report["all_nonterminal_pod_objects"])
    print("POD_PHASE_COUNTS=" + json.dumps(report["phases"], sort_keys=True))
    print("")
    print("=== NODE POD CAPACITY (assigned nonterminal, not dashboard pod count) ===")
    for n in report["nodes"]:
        print(f"NODE={n['name']} ASSIGNED_ACTIVE_OR_PENDING={n['assigned']} ALLOCATABLE_PODS={n['allocatable']} REMAINING={n['remaining']}")
    print("")
    print("=== NAMESPACE POD COUNTS (highest active first) ===")
    print("NAMESPACE\tNONTERMINAL_ASSIGNED\tRUNNING\tPENDING\tTERMINAL_HISTORY\tOBJECTS_ALL\tSCOPE")
    for n in report["namespace_rows"]:
        print(f"{n['namespace']}\t{n.get('assigned_nonterminal', 0)}\t{n.get('running', 0)}\t{n.get('pending', 0)}\t{n.get('terminal', 0)}\t{n['objects']}\t{'PROTECTED' if n['protected'] else 'REVIEW_ONLY'}")
    print("")
    print("=== TERMINAL HISTORICAL BUILDS (NOT FREE POD SLOTS CLAIMS) ===")
    for name, b in sorted(report["historical_builds"].items()):
        print(f"BUILD_NAMESPACE={name} BUILD_TOTAL={b.get('build_total', 0)} BUILD_TERMINAL={b.get('build_terminal', 0)} BUILD_NONTERMINAL={b.get('build_nonterminal', 0)}")
    print("")
    print("=== TRADEOPS EPHEMERAL DATA MOUNTS (DO NOT RECREATE THESE PODS) ===")
    for name, container, mount, phase in report["tradeops_ephemeral_mounts"]:
        print(f"TRADEOPS_EMPTYDIR_POD={name} CONTAINER={container} MOUNT={mount} PHASE={phase}")
    print(f"TRADEOPS_EPHEMERAL_MOUNT_COUNT={len(report['tradeops_ephemeral_mounts'])}")
    print("RESULT=INVENTORY_ONLY_NO_CLEANUP_APPROVAL")
    print("NEXT=Review the counts and persistence risks before any scale/delete/CRC stop.")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-top", action="store_true", help="skip best-effort oc adm top nodes")
    args = parser.parse_args(argv)
    try:
        pods = run_readonly(["oc", "get", "pods", "-A", "-o", "json"])
        nodes = run_readonly(["oc", "get", "nodes", "-o", "json"])
        report = count_pods(pods, nodes)
        print_report(report)
        if not args.no_top:
            print("\n=== oc adm top nodes: CPU/memory point in time (best effort) ===")
            proc = subprocess.run(["oc", "adm", "top", "nodes"], capture_output=True, text=True, check=False, timeout=30)
            print(proc.stdout.rstrip() if proc.returncode == 0 else "TOP_NODES=NOT_AVAILABLE")
        return 0
    except (OSError, subprocess.TimeoutExpired, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"AUDIT_FAILED_READONLY={str(exc)[:320]}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

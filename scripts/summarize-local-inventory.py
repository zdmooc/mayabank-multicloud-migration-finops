#!/usr/bin/env python3
"""Offline numeric summary of collector CSVs. Never prints node/pod/namespace names."""
import argparse
import csv
from pathlib import Path
from collections import Counter

def records(root, filename):
    with (root / filename).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def cpu_m(q):
    q = (q or "").strip()
    if not q: return 0.0
    for suffix, factor in (("m",1),("u",0.001),("n",0.000001)):
        if q.endswith(suffix): return float(q[:-1])*factor
    return float(q)*1000

def memory_mi(q):
    q = (q or "").strip()
    if not q: return 0.0
    for suffix, factor in (("Ki",1/1024),("Mi",1),("Gi",1024),("Ti",1048576),
                           ("K",1000/1048576),("M",1e6/1048576),
                           ("G",1e9/1048576),("T",1e12/1048576)):
        if q.endswith(suffix): return float(q[:-len(suffix)])*factor
    return float(q)/1048576

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path, help="Local evidence/local/private-* path")
    p.add_argument("--workload-groups", action="store_true",
                   help="Show only safe aggregate resource sums for known synthetic MayaBank workstream categories; no namespace names")
    a = p.parse_args()
    try:
        pods = records(a.directory, "pod-resources.csv")
        pvcs = records(a.directory, "pvc-requests.csv")
        nodes = records(a.directory, "node-allocatable.csv")
        phases = Counter({(r["namespace"], r["pod"]): r["phase"] for r in pods}.values())
        active = [r for r in pods if r["phase"] in {"Running","Pending"}]
        running = [r for r in pods if r["phase"] == "Running"]
        total_cpu = sum(cpu_m(r["cpu_request"]) for r in active)
        total_mem = sum(memory_mi(r["memory_request"]) for r in active)
        running_cpu = sum(cpu_m(r["cpu_request"]) for r in running)
        running_mem = sum(memory_mi(r["memory_request"]) for r in running)
        items = {
            "node_count":len(nodes),
            "node_allocatable_vcpu":sum(cpu_m(r["allocatable_cpu"]) for r in nodes)/1000,
            "node_allocatable_gib":sum(memory_mi(r["allocatable_memory"]) for r in nodes)/1024,
            "pod_count":sum(phases.values()),
            "pod_states":",".join(f"{k}:{v}" for k,v in sorted(phases.items())),
            "active_running_pending_container_count":len(active),
            "active_requests_cpu_m":total_cpu,
            "active_requests_memory_mi":total_mem,
            "running_requests_cpu_m":running_cpu,
            "running_requests_memory_mi":running_mem,
            "active_containers_missing_cpu_request":sum(not r["cpu_request"] for r in active),
            "active_containers_missing_memory_request":sum(not r["memory_request"] for r in active),
            "pvc_count":len(pvcs),
            "pvc_bound_count":sum(r["phase"]=="Bound" for r in pvcs),
            "pvc_requested_gib":sum(memory_mi(r["requested_storage"]) for r in pvcs)/1024,
        }
        alloc_cpu_m = sum(cpu_m(r["allocatable_cpu"]) for r in nodes)
        alloc_mem_mi = sum(memory_mi(r["allocatable_memory"]) for r in nodes)
        if alloc_cpu_m > 0 and alloc_mem_mi > 0:
            items.update({
                "active_requests_cpu_pct_allocatable": total_cpu / alloc_cpu_m * 100,
                "active_requests_memory_pct_allocatable": total_mem / alloc_mem_mi * 100,
                "running_requests_cpu_pct_allocatable": running_cpu / alloc_cpu_m * 100,
                "running_requests_memory_pct_allocatable": running_mem / alloc_mem_mi * 100,
                "headroom_after_active_requests_cpu_m": alloc_cpu_m - total_cpu,
                "headroom_after_active_requests_memory_mi": alloc_mem_mi - total_mem,
            })
        pending = [r for r in pods if r["phase"] == "Pending"]
        items["pending_container_cpu_request_m"] = sum(cpu_m(r["cpu_request"]) for r in pending)
        items["pending_container_memory_request_mi"] = sum(memory_mi(r["memory_request"]) for r in pending)
        # Namespace prefixes are only aggregated as category counts and resource sums.
        # No pod, node, container or namespace identifiers are printed.
        for group, selected in (
            ("openshift_prefix", [r for r in active if r["namespace"].startswith("openshift-")]),
            ("other_namespace_prefix", [r for r in active if not r["namespace"].startswith("openshift-")]),
        ):
            items[group + "_active_pods"] = len({(r["namespace"], r["pod"]) for r in selected})
            items[group + "_active_requests_cpu_m"] = sum(cpu_m(r["cpu_request"]) for r in selected)
            items[group + "_active_requests_memory_mi"] = sum(memory_mi(r["memory_request"]) for r in selected)
        for k,v in items.items():
            print(f"{k}={v:.2f}" if isinstance(v,float) else f"{k}={v}")
        if a.workload_groups:
            # Deliberately explicit synthetic workload classification, not a
            # platform ownership guarantee. Unknown namespaces are aggregated.
            # Never print raw namespace/pod names or serialize original CSVs.
            known = {
                "instant-payments-local": "product_payments",
                "tradeops": "product_tradeops",
                "maya-freelance": "product_freelance",
                "mayainsurance-decision-local": "product_decision",
                "mayabank-mq-local": "specialized_mq",
                "keycloak-system": "shared_identity",
                "mayabank-api": "mixed_api_gateway_and_product",
                "shared-observability": "shared_otel",
                "shared-platform-services": "shared_platform_operator",
                "hostpath-provisioner": "local_lab_storage",
            }
            groups = {}
            for r in active:
                namespace = r["namespace"]
                group = ("openshift_prefix_all" if namespace.startswith("openshift-")
                         else known.get(namespace, "unclassified_other"))
                groups.setdefault(group, []).append(r)
            print("WORKLOAD_GROUPS=synthetic_explicit_mapping_EXPERIMENTAL")
            for group in sorted(groups):
                entries = groups[group]
                pods_in_group = len({(r["namespace"], r["pod"]) for r in entries})
                requested_cpu = sum(cpu_m(r["cpu_request"]) for r in entries)
                requested_mem = sum(memory_mi(r["memory_request"]) for r in entries)
                print(f"group_{group}_pods={pods_in_group}")
                print(f"group_{group}_requests_cpu_m={requested_cpu:.2f}")
                print(f"group_{group}_requests_memory_mi={requested_mem:.2f}")
            print("GROUP_CAVEAT=not_a_cloud_migration_target_or_live_utilization")

        print("SCOPE=declared_requests_only_NOT_measured_CPU_RAM_or_P95")
        print("CAUTION=running_plus_pending_requests_NOT_equivalent_to_scheduled_node_reservations")
        print("NAMESPACE_GROUPS=prefix_categories_only_NOT_exact_managed_cloud_system_overhead")
        print("PVC_SCOPE=requested_size_NOT_used_bytes")
    except (OSError, ValueError, KeyError):
        p.error("CSV missing or invalid; confirm local collector directory and format")

if __name__=="__main__":
    main()

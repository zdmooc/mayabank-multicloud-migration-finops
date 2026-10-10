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
        for k,v in items.items():
            print(f"{k}={v:.2f}" if isinstance(v,float) else f"{k}={v}")
        print("SCOPE=declared_requests_only_NOT_measured_CPU_RAM_or_P95")
        print("PVC_SCOPE=requested_size_NOT_used_bytes")
    except (OSError, ValueError, KeyError):
        p.error("CSV missing or invalid; confirm local collector directory and format")

if __name__=="__main__":
    main()

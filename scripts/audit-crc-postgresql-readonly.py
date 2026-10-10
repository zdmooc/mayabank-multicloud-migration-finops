#!/usr/bin/env python3
"""Read-only local CRC PostgreSQL topology/FinOps audit; no Secret values exported.

Usage: python scripts/audit-crc-postgresql-readonly.py
Only oc get and oc adm top are called. Detailed reports remain under ignored evidence/local/.
Requires Python 3.10+ and an authenticated oc client. No databases are contacted.
"""
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

PG = re.compile(r"postgres|postgis|timescale|pgvector|spilo|cnpg", re.I)
DB_ENV = re.compile(r"POSTGRES|PGHOST|JDBC|DATASOURCE|DATABASE|KC_DB|DB_", re.I)
HOST_ENV = re.compile(r"(^PGHOST$|POSTGRES.*HOST|DATABASE.*HOST|DB_.*HOST|KC_DB_URL|JDBC.*URL|DATASOURCE.*URL|DATABASE_URL$)", re.I)
SENSITIVE = re.compile(r"PASS|TOKEN|SECRET|KEY|CREDENTIAL|AUTH", re.I)
DNS = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
EXPECTED = {
    ("instant-payments-local", "postgresql-acceptor"),
    ("instant-payments-local", "postgresql-consumer"),
    ("instant-payments-local", "postgresql-payments"),
    ("maya-freelance", "postgres"),
    ("mayabank-mq-local", "payments-db"),
    ("wero-poc", "postgresql"),
    ("keycloak-system", "postgresql"),
    ("openshift-pipelines", "tekton-results-postgres"),
    ("tradeops", "postgres"),
}

def oc_json(*args):
    p = subprocess.run(["oc", *args, "-o", "json"], capture_output=True, text=True, check=True)
    return json.loads(p.stdout).get("items", [])

def top_now():
    p = subprocess.run(["oc", "adm", "top", "pods", "-A", "--containers"],
                       capture_output=True, text=True)
    if p.returncode:
        return {}, "UNAVAILABLE"
    out = {}
    for line in p.stdout.splitlines():
        fields = line.split()
        if len(fields) == 5 and fields[0] != "NAMESPACE":
            try:
                out[tuple(fields[:3])] = (to_cpu(fields[3]), to_mi(fields[4]))
            except ValueError:
                continue
    return out, "SINGLE_SAMPLE" if out else "UNAVAILABLE"

def to_cpu(s):
    if not s:
        return 0.
    for unit, mul in (("m", 1.), ("u", .001), ("n", .000001)):
        if s.endswith(unit):
            return float(s[:-len(unit)]) * mul
    return float(s) * 1000

def to_mi(s):
    if not s:
        return 0.
    for unit, mul in (("Ki", 1/1024), ("Mi", 1), ("Gi", 1024), ("Ti", 1024*1024),
                      ("K", 1000/1048576), ("M", 1000000/1048576),
                      ("G", 1000000000/1048576)):
        if s.endswith(unit):
            return float(s[:-len(unit)]) * mul
    return float(s)/1048576

def safe_host(env):
    """Return only a standalone non-sensitive hostname, never a URL or userinfo."""
    key = env.get("name", "")
    if SENSITIVE.search(key) or not HOST_ENV.search(key):
        return None
    v = env.get("value")
    if not isinstance(v, str) or not v:
        return None
    if "://" in v:
        candidate = v.split("://", 1)[1]
        try:
            host = urlsplit("scheme://" + candidate).hostname
        except ValueError:
            return None
    else:
        host = v
    if host and len(host) <= 253 and DNS.fullmatch(host) and ":" not in host:
        return host.lower().rstrip(".")
    return None

def matching(selector, labels):
    return bool(selector) and all(labels.get(k) == v for k, v in selector.items())

def main():
    os.umask(0o077)
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python scripts/audit-crc-postgresql-readonly.py [output-dir]")
    root = Path(sys.argv[1]) if len(sys.argv) == 2 else Path(
        "evidence/local/private-postgresql-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if not str(root).replace("\\", "/").startswith("evidence/local/private-"):
        raise SystemExit("Output must be under evidence/local/private-* (ignored by git).")
    root.mkdir(parents=True, exist_ok=False)
    try:
        workloads = oc_json("get", "deployments,statefulsets", "-A")
        pods = oc_json("get", "pods", "-A")
        replicasets = oc_json("get", "replicasets", "-A")
        services = oc_json("get", "services", "-A")
        pvcs = oc_json("get", "pvc", "-A")
        pvs = oc_json("get", "pv")
        metrics, metrics_status = top_now()
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError) as exc:
        raise SystemExit("Failed to read CRC resources; no resource changes attempted: " + type(exc).__name__) from None

    def key(item):
        return item.get("metadata", {}).get("namespace", ""), item["metadata"]["name"]

    rs_owner = {}
    for rs in replicasets:
        owners = rs.get("metadata", {}).get("ownerReferences", [])
        dep = next((o["name"] for o in owners if o.get("kind") == "Deployment"), None)
        if dep:
            rs_owner[key(rs)] = dep
    pods_by_workload = {}
    for pod in pods:
        ns, name = key(pod)
        owners = pod.get("metadata", {}).get("ownerReferences", [])
        owner = next((o for o in owners if o.get("kind") in ("ReplicaSet", "StatefulSet")), None)
        if not owner:
            continue
        owner_name = rs_owner.get((ns, owner["name"])) if owner["kind"] == "ReplicaSet" else owner["name"]
        if owner_name:
            pods_by_workload.setdefault((ns, owner_name), []).append(pod)

    servers = {}
    for w in workloads:
        ns, name = key(w)
        containers = w.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        if not (PG.search(name) or any(PG.search(c.get("image", "")) for c in containers)):
            continue
        servers[(ns, name)] = w
    pv_by_name = {p["metadata"]["name"]: p for p in pvs}
    pvc_by_name = {key(p): p for p in pvcs}
    service_to_server = {}
    for s in services:
        ns, svc_name = key(s)
        selector = s.get("spec", {}).get("selector") or {}
        matched = [name for (server_ns, name), w in servers.items()
                   if ns == server_ns and matching(
                       selector, w.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}))]
        if len(matched) == 1:
            service_to_server[(ns, svc_name)] = matched[0]

    rows = []
    for (ns, name), w in sorted(servers.items()):
        attached = pods_by_workload.get((ns, name), [])
        spec = w.get("spec", {})
        tmpl = spec.get("template", {}).get("spec", {})
        imgs = [c.get("image", "") for c in tmpl.get("containers", [])]
        claim_names = [v["persistentVolumeClaim"]["claimName"] for v in tmpl.get("volumes", [])
                       if "persistentVolumeClaim" in v]
        claim_reports = []
        for cname in claim_names:
            claim = pvc_by_name.get((ns, cname), {})
            pv_name = claim.get("spec", {}).get("volumeName", "")
            pv = pv_by_name.get(pv_name, {})
            claim_reports.append("{}:{}:{}:{}:{}".format(
                cname, claim.get("status", {}).get("phase", "UNKNOWN"),
                claim.get("spec", {}).get("resources", {}).get("requests", {}).get("storage", "?"),
                pv.get("spec", {}).get("persistentVolumeReclaimPolicy", "?"),
                pv_name or "?"))
        requested_cpu = requested_mem = measured_cpu = measured_mem = 0.
        matched = running_containers = 0
        for pod in attached:
            if pod.get("status", {}).get("phase") != "Running":
                continue
            for c in pod.get("spec", {}).get("containers", []):
                running_containers += 1
                req = c.get("resources", {}).get("requests") or {}
                requested_cpu += to_cpu(req.get("cpu", ""))
                requested_mem += to_mi(req.get("memory", ""))
                sample = metrics.get((ns, pod["metadata"]["name"], c.get("name")))
                if sample:
                    matched += 1
                    measured_cpu += sample[0]
                    measured_mem += sample[1]
        rows.append({
            "namespace": ns, "kind": w.get("kind", "?"), "workload": name,
            "desired": spec.get("replicas", 1), "ready": w.get("status", {}).get("readyReplicas", 0),
            "running_pods": sum(p.get("status", {}).get("phase") == "Running" for p in attached),
            "image": ";".join(imgs), "pvc": ";".join(claim_reports) or "NONE_DECLARED",
            "running_container_request_cpu_m": round(requested_cpu, 2),
            "running_container_request_mem_mi": round(requested_mem, 2),
            "top_coverage": "{}/{}".format(matched, running_containers),
            "top_cpu_m": round(measured_cpu, 2) if matched else "NA",
            "top_mem_mi": round(measured_mem, 2) if matched else "NA",
        })

    links = []
    for w in workloads:
        ns, name = key(w)
        if (ns, name) in servers:
            continue
        tmpl = w.get("spec", {}).get("template", {}).get("spec", {})
        for c in tmpl.get("containers", []):
            for e in c.get("env", []):
                label = e.get("name", "")
                if not DB_ENV.search(label) or SENSITIVE.search(label):
                    continue
                host = safe_host(e)
                if host:
                    parts = host.split(".")
                    host_ns = parts[1] if len(parts) > 2 and parts[2] == "svc" else ns
                    dest = service_to_server.get((host_ns, parts[0]))
                    status = "SVC_SELECTOR_CANDIDATE_NOT_PROVEN_SQL" if dest else "UNRESOLVED_LITERAL_HOST"
                    if dest:
                        links.append({"consumer_ns": ns, "consumer": name, "variable": label,
                                      "server_ns": host_ns, "server": dest, "evidence": status})
                    else:
                        links.append({"consumer_ns": ns, "consumer": name, "variable": label,
                                      "server_ns": "", "server": "", "evidence": status})
                elif e.get("valueFrom") or label.upper().endswith(("HOST", "URL")):
                    links.append({"consumer_ns": ns, "consumer": name, "variable": label,
                                  "server_ns": "", "server": "", "evidence": "UNRESOLVED_CONFIG_OR_REF"})
            if c.get("envFrom"):
                links.append({"consumer_ns": ns, "consumer": name, "variable": "envFrom",
                              "server_ns": "", "server": "", "evidence": "UNRESOLVED_ENVFROM"})
    def write_csv(fname, data, cols):
        with (root / fname).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=cols)
            writer.writeheader()
            writer.writerows(data)

    write_csv("postgresql-workloads.csv", rows, [
        "namespace", "kind", "workload", "desired", "ready", "running_pods", "image", "pvc",
        "running_container_request_cpu_m", "running_container_request_mem_mi",
        "top_coverage", "top_cpu_m", "top_mem_mi"])
    write_csv("database-consumer-candidates.csv", links, [
        "consumer_ns", "consumer", "variable", "server_ns", "server", "evidence"])
    summary = [
        "POSTGRES_AUDIT=READ_ONLY",
        "TARGET=CRC_K8S_DECLARED_WORKLOADS_NOT_LOGICAL_DATABASES",
        "WORKLOAD_COUNT={}".format(len(rows)),
        "DESIRED_REPLICAS={}".format(sum(int(r["desired"]) for r in rows)),
        "READY_REPLICAS={}".format(sum(int(r["ready"]) for r in rows)),
        "EXPECTED_NINE_PRESENT={}".format(EXPECTED.issubset(set(servers))),
        "METRICS={}".format(metrics_status),
        "TOP_MATCHED_PG_CONTAINERS={}".format(sum(int(r["top_coverage"].split("/")[0]) for r in rows)),
        "TOP_RUNNING_PG_CONTAINERS={}".format(sum(int(r["top_coverage"].split("/")[1]) for r in rows)),
        "CANDIDATE_SVC_LINKS={}".format(sum(x["evidence"].startswith("SVC_SELECTOR") for x in links)),
        "UNRESOLVED_CONNECTION_VARIABLES={}".format(sum(x["evidence"].startswith("UNRESOLVED") for x in links)),
        "NO_SECRET_VALUES_SERIALIZED=true",
        "PVC_CAPACITY_IS_NOT_DISK_USAGE=true",
        "CLIENT_CONFIG_DOES_NOT_PROVE_OPEN_SQL_CONNECTIONS=true",
        "TOP_IS_SINGLE_SAMPLE_NOT_P95=true",
        "NO_K8S_MUTATIONS=true",
    ]
    (root / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    print("LOCAL_PRIVATE_OUTPUT=" + str(root))
    print("Review local CSV names/network metadata before sharing; directory is gitignored.")
if __name__ == "__main__":
    main()

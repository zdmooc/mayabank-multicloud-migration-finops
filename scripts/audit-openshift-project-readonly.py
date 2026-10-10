#!/usr/bin/env python3
"""Generic, read-only OpenShift/CRC project audit (Python 3.10+, standard library).

No cluster mutations, SQL access, Secrets, ConfigMap content, or live network probes.
Raw Kubernetes JSON is processed in-memory, never saved. Reports stay on local disk.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys

SAFE_NS = re.compile(r"^[a-z0-9](?:[-a-z0-9]*[a-z0-9])?$")
DB_IMAGE = re.compile(r"postgres|mysql|mariadb|mongo|redis|kafka|redpanda|qdrant|elastic|opensearch|cockroach|cassandra", re.I)
DB_HOST_KEY = re.compile(r"^(PGHOST|POSTGRES_HOST|POSTGRESQL_HOST|DB_HOST|DB_POSTGRESDB_HOST|KC_DB_URL_HOST|DATABASE_HOST|.*_DB_HOST|.*_DATABASE_HOST)$", re.I)
GITOPS_NS = "openshift-gitops"


def run(args: list[str], timeout=60) -> tuple[bool, str]:
    try:
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode == 0, p.stdout if p.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return False, ""


def get_obj(ns: str | None, res: str, name: str | None = None):
    args = ["oc", "get", res]
    if name:
        args.append(name)
    if ns:
        args.extend(["-n", ns])
    args.extend(["-o", "json"])
    ok, output = run(args)
    if not ok:
        return None
    try:
        return json.loads(output)
    except (ValueError, TypeError):
        return None


def get_items(ns, res):
    obj = get_obj(ns, res)
    return obj.get("items", []) if isinstance(obj, dict) else []


def m(item, k, default=None):
    return (item or {}).get("metadata", {}).get(k, default)


def to_cpu(value):
    s = str(value or "").strip()
    if not s:
        return 0.0
    for unit, factor in (("m", 1), ("u", .001), ("n", .000001)):
        if s.endswith(unit):
            return float(s[:-len(unit)]) * factor
    return float(s) * 1000


def to_mem(value):
    s = str(value or "").strip()
    if not s:
        return 0.0
    for unit, factor in (("Ki", 1/1024), ("Mi", 1), ("Gi", 1024), ("Ti", 1048576),
                         ("K", 1000/1048576), ("M", 1000000/1048576), ("G", 1e9/1048576)):
        if s.endswith(unit):
            return float(s[:-len(unit)]) * factor
    return float(s)/1048576


def parse_top(output, ns):
    """Accept both `-n ns` (4 columns) and all-namespaces (5 columns)."""
    results = {}
    for line in output.splitlines():
        fields = line.split()
        if not fields or fields[0] in ("NAMESPACE", "POD", "NAME"):
            continue
        try:
            if len(fields) == 4:
                pod, container, cpu, mem = fields
                namespace = ns
            elif len(fields) == 5:
                namespace, pod, container, cpu, mem = fields
            else:
                continue
            results[(namespace, pod, container)] = [round(to_cpu(cpu), 4), round(to_mem(mem), 4)]
        except ValueError:
            continue
    return results


def add_finding(out, level, code, detail, proof):
    out.append({"severity": level, "code": code, "detail": detail, "evidence": proof})


def workload_id(x):
    return (m(x, "namespace"), m(x, "name"))


def owner_map(replica_sets):
    return {(m(rs, "namespace"), m(rs, "name")): next((o["name"] for o in m(rs, "ownerReferences", [])
            if o.get("kind") == "Deployment"), None) for rs in replica_sets}


def pod_owner(pod, rs_map):
    namespace = m(pod, "namespace")
    for o in m(pod, "ownerReferences", []):
        if o.get("kind") == "ReplicaSet":
            return "Deployment", rs_map.get((namespace, o.get("name")))
        if o.get("kind") in ("StatefulSet", "DaemonSet", "Job"):
            return o.get("kind"), o.get("name")
    return "", ""


def safe_host_env(env):
    """Only literal, simple in-namespace service hosts. No URL/password extraction."""
    name = env.get("name", "")
    value = env.get("value")
    if DB_HOST_KEY.match(name) and isinstance(value, str):
        value = value.strip().lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9.\-]{0,252}", value):
            return value
    return None


def local_repo(path):
    if not path:
        return {"checked": False}
    root = Path(path).resolve()
    if not root.is_dir():
        return {"checked": True, "available": False}
    ok, head = run(["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"])
    ok2, status = run(["git", "-C", str(root), "status", "--porcelain"])
    def count(pattern):
        return len(list(root.glob(pattern)))
    return {"checked": True, "available": True, "git_head": head.strip() if ok else "UNKNOWN",
            "uncommitted_entries": len(status.splitlines()) if ok2 else "UNKNOWN",
            "readme": (root / "README.md").exists(),
            "github_workflows": count(".github/workflows/*.yml") + count(".github/workflows/*.yaml"),
            "dockerfiles": count("**/Dockerfile"), "test_files": count("tests/**/test_*.py") + count("tests/**/test_*.sh"),
            "helm_charts": count("**/Chart.yaml"), "kustomizations": count("**/kustomization.yaml"),
            "terraform_files": count("**/*.tf"),
            "limitation": "Inventory of files only; no code, CI, supply-chain or test execution review"}


def analyze_namespace(ns, repo_path=None, include_gitops=False):
    namespace = get_obj(None, "namespace", ns)
    if not namespace:
        raise RuntimeError(f"Namespace inaccessible or missing: {ns}")
    lists = {}
    kinds = {
        "deployments": "deployments", "statefulsets": "statefulsets", "daemonsets": "daemonsets",
        "jobs": "jobs", "cronjobs": "cronjobs", "replicasets": "replicasets",
        "pods": "pods", "services": "services", "routes": "routes.route.openshift.io",
        "ingresses": "ingresses.networking.k8s.io", "networkpolicies": "networkpolicies.networking.k8s.io",
        "pvc": "pvc", "hpa": "hpa", "pdb": "pdb", "quotas": "resourcequotas",
        "limitranges": "limitranges", "serviceaccounts": "serviceaccounts", "rolebindings": "rolebindings",
        "events": "events"
    }
    unavailable = []
    for name, resource in kinds.items():
        obj = get_obj(ns, resource)
        if obj is None:
            unavailable.append(name)
        lists[name] = (obj or {}).get("items", [])

    rsmap = owner_map(lists["replicasets"])
    attached = collections.defaultdict(list)
    for p in lists["pods"]:
        typ, owner = pod_owner(p, rsmap)
        if owner:
            attached[(typ, owner)].append(p)

    top_ok, top_txt = run(["oc", "adm", "top", "pods", "-n", ns, "--containers"])
    top = parse_top(top_txt, ns) if top_ok else {}
    findings = []
    workloads = []
    used_pvc = set()
    total_cpu_req = total_mem_req = total_cpu_obs = total_mem_obs = 0.0
    top_match = top_expected = 0
    for kind in ("deployments", "statefulsets", "daemonsets"):
        for w in lists[kind]:
            nm = m(w, "name")
            type_name = {"deployments": "Deployment", "statefulsets": "StatefulSet", "daemonsets": "DaemonSet"}[kind]
            desired = w.get("spec", {}).get("replicas", 1) if kind != "daemonsets" else w.get("status", {}).get("desiredNumberScheduled", 0)
            ready = w.get("status", {}).get("readyReplicas", 0) if kind != "daemonsets" else w.get("status", {}).get("numberReady", 0)
            template = w.get("spec", {}).get("template", {}).get("spec", {})
            containers = template.get("containers", [])
            volumes = template.get("volumes", [])
            claims = sorted({v["persistentVolumeClaim"].get("claimName") for v in volumes if "persistentVolumeClaim" in v})
            ephemeral = {v.get("name") for v in volumes if "emptyDir" in v}
            paths = []
            for c in containers:
                for mount in c.get("volumeMounts", []) or []:
                    if mount.get("name") in ephemeral:
                        paths.append(mount.get("mountPath", "UNKNOWN"))
            for pod in attached.get((type_name, nm), []):
                for v in pod.get("spec", {}).get("volumes", []) or []:
                    if "persistentVolumeClaim" in v:
                        claims.append(v["persistentVolumeClaim"].get("claimName"))
                for c in pod.get("spec", {}).get("containers", []):
                    for mount in c.get("volumeMounts", []) or []:
                        if mount.get("name") in {v.get("name") for v in pod.get("spec", {}).get("volumes", []) if "emptyDir" in v}:
                            paths.append(mount.get("mountPath", "UNKNOWN"))
            used_pvc.update(x for x in claims if x)
            if ready < desired:
                add_finding(findings, "P1", "WORKLOAD_NOT_READY", f"{type_name}/{nm}: {ready}/{desired}", "Ready/desired status")
            if desired == 0:
                add_finding(findings, "INFO", "WORKLOAD_SCALE_ZERO", f"{type_name}/{nm}", "spec.replicas=0")
            db_workload = bool(DB_IMAGE.search(nm) or any(DB_IMAGE.search(c.get("image", "")) for c in containers))
            data_mounts = [p for p in paths if re.search(r"(^/data$|postgres|mysql|redpanda|kafka|mongo|redis|qdrant|/data/|/var/lib/)", p, re.I)]
            if db_workload and data_mounts and type_name == "StatefulSet":
                add_finding(findings, "P0", "EPHEMERAL_STATEFUL_DATA",
                            f"{type_name}/{nm} uses emptyDir at {', '.join(sorted(set(data_mounts)))}; pod replacement may lose data",
                            "Pod/StatefulSet volume and volumeMount specification")
            elif db_workload and paths and type_name == "StatefulSet":
                add_finding(findings, "P2", "STATEFUL_EMPTYDIR_REVIEW",
                            f"{type_name}/{nm} uses emptyDir at {', '.join(sorted(set(paths)))}; verify it is only cache",
                            "Pod/StatefulSet mount specification")
            for c in containers:
                img = c.get("image", "")
                if img.endswith(":latest") or (":" not in img.rsplit("/", 1)[-1] and "@sha256:" not in img):
                    add_finding(findings, "P2", "IMAGE_NOT_IMMUTABLE", f"{type_name}/{nm} container {c.get('name')}", "image tag is floating")
                if not c.get("readinessProbe"):
                    add_finding(findings, "P2", "READINESS_PROBE_ABSENT", f"{type_name}/{nm} container {c.get('name')}", "container spec")
                if not c.get("resources", {}).get("requests", {}).get("memory"):
                    add_finding(findings, "P2", "MEMORY_REQUEST_MISSING", f"{type_name}/{nm} container {c.get('name')}", "container resource requests")
                sec = c.get("securityContext") or {}
                if sec.get("privileged") is True:
                    add_finding(findings, "P1", "PRIVILEGED_CONTAINER", f"{type_name}/{nm} container {c.get('name')}", "securityContext.privileged=true")
            wc = wm = oc = om = 0.0
            current_running = [pod for pod in attached.get((type_name, nm), []) if pod.get("status", {}).get("phase") == "Running"]
            for p in current_running:
                for c in p.get("spec", {}).get("containers", []):
                    req = (c.get("resources") or {}).get("requests") or {}
                    try:
                        wc += to_cpu(req.get("cpu", ""))
                        wm += to_mem(req.get("memory", ""))
                    except ValueError:
                        pass
                    top_expected += 1
                    data = top.get((ns, m(p, "name"), c.get("name")))
                    if data:
                        top_match += 1
                        oc += data[0]
                        om += data[1]
            total_cpu_req += wc
            total_mem_req += wm
            total_cpu_obs += oc
            total_mem_obs += om
            workloads.append({"kind": type_name, "name": nm, "desired": desired, "ready": ready,
                              "running_pods": len(current_running), "images": [c.get("image", "") for c in containers],
                              "pvc_claims": sorted(set(claims)), "emptydir_mounts": sorted(set(paths)),
                              "cpu_req_m": round(wc, 3), "ram_req_mi": round(wm, 3),
                              "top_cpu_m_if_covered": round(oc, 3), "top_ram_mi_if_covered": round(om, 3)})
    for p in lists["pods"]:
        for stat in p.get("status", {}).get("containerStatuses", []) or []:
            if stat.get("restartCount", 0) >= 3:
                add_finding(findings, "P2", "RESTARTS", f"Pod/{m(p,'name')} container {stat.get('name')} restarts={stat.get('restartCount')}", "status.containerStatuses")
            wait = (stat.get("state") or {}).get("waiting") or {}
            terminated = (stat.get("lastState") or {}).get("terminated") or {}
            if wait.get("reason") in ("CrashLoopBackOff", "ImagePullBackOff", "ErrImagePull"):
                add_finding(findings, "P1", "POD_WAITING", f"Pod/{m(p,'name')} reason={wait.get('reason')}", "container state")
            if terminated.get("reason") == "OOMKilled":
                add_finding(findings, "P1", "OOM_KILLED", f"Pod/{m(p,'name')} container {stat.get('name')}", "container lastState")
    pvcs = []
    for x in lists["pvc"]:
        nm = m(x, "name")
        pv_name = x.get("spec", {}).get("volumeName", "")
        volume = get_obj(None, "pv", pv_name) if pv_name else None
        reclaim = (volume or {}).get("spec", {}).get("persistentVolumeReclaimPolicy", "UNKNOWN")
        phase = (x.get("status") or {}).get("phase", "UNKNOWN")
        if phase != "Bound":
            add_finding(findings, "P1", "PVC_NOT_BOUND", f"PVC/{nm} is {phase}", "PVC.status.phase")
        if reclaim == "Delete":
            add_finding(findings, "P2", "PV_RECLAIM_DELETE", f"PVC/{nm} uses PV reclaim=Delete; ensure independent backup", "PV.spec.persistentVolumeReclaimPolicy")
        pvcs.append({"name": nm, "phase": phase, "requested": x.get("spec", {}).get("resources", {}).get("requests", {}).get("storage", ""),
                     "capacity": x.get("status", {}).get("capacity", {}).get("storage", ""),
                     "storageclass": x.get("spec", {}).get("storageClassName"), "reclaim": reclaim,
                     "volume": pv_name, "used_by_template": nm in used_pvc,
                     "actual_used_bytes": "NOT_MEASURED"})
    if not lists["networkpolicies"] and workloads:
        add_finding(findings, "P1", "NO_NETWORK_POLICIES", "No NetworkPolicy objects in namespace", "NetworkPolicy objects returned by API")
    if not lists["quotas"]:
        add_finding(findings, "P2", "NO_RESOURCE_QUOTA", "No ResourceQuota object", "ResourceQuota list")
    if not lists["limitranges"]:
        add_finding(findings, "P2", "NO_LIMIT_RANGE", "No LimitRange object", "LimitRange list")
    for cj in lists["cronjobs"]:
        if cj.get("spec", {}).get("suspend") is not True:
            add_finding(findings, "INFO", "CRONJOB_ENABLED", f"CronJob/{m(cj,'name')} may schedule new pods", "CronJob.spec.suspend")
    hpa_targets = {((h.get("spec") or {}).get("scaleTargetRef") or {}).get("name") for h in lists["hpa"]}
    pdb_selectors = [p.get("spec", {}).get("selector", {}).get("matchLabels", {}) for p in lists["pdb"]]
    for w in lists["deployments"] + lists["statefulsets"]:
        name = m(w, "name")
        replicas = w.get("spec", {}).get("replicas", 1)
        podlabels = w.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {})
        if replicas > 1 and not any(sel and all(podlabels.get(k) == v for k, v in sel.items()) for sel in pdb_selectors):
            add_finding(findings, "P2", "PDB_NOT_IDENTIFIED", f"{w.get('kind')}/{name} replicas={replicas}; no matching PDB selector", "PDB selectors and desired replicas")
        if name in hpa_targets:
            add_finding(findings, "INFO", "HPA_PRESENT", f"{w.get('kind')}/{name} HPA exists; manual scale may conflict", "HPA.spec.scaleTargetRef")
    exposed_services = [m(s, "name") for s in lists["services"] if s.get("spec", {}).get("type") in ("LoadBalancer", "NodePort")]
    if exposed_services:
        add_finding(findings, "P2", "EXTERNALLY_EXPOSED_SERVICES", f"{len(exposed_services)} NodePort/LoadBalancer services to review", "Service.spec.type")
    services = []
    for s in lists["services"]:
        if s.get("spec", {}).get("type") == "ExternalName":
            continue
        sel = s.get("spec", {}).get("selector", {}) or {}
        targets = [w["name"] for w in workloads if sel and any(m(src, "name") == w["name"] and
                   src.get("spec", {}).get("template", {}).get("metadata", {}).get("labels", {}) and
                   all(src["spec"]["template"]["metadata"]["labels"].get(k) == v for k, v in sel.items())
                   for src in (lists["deployments"] + lists["statefulsets"] + lists["daemonsets"]))]
        services.append({"name": m(s, "name"), "type": s.get("spec", {}).get("type", "ClusterIP"),
                         "workload_candidates": sorted(set(targets)), "selector_present": bool(sel),
                         "ports": sorted({str(p.get("port")) + "/" + str(p.get("protocol", "TCP"))
                                          for p in s.get("spec", {}).get("ports", []) if p.get("port") is not None})})
    # Route hostname is deliberately NOT exported. Only its Service target and
    # TLS termination mode are needed for an offline topology drawing.
    routes = []
    for route in lists["routes"]:
        spec = route.get("spec", {})
        tls = spec.get("tls") or {}
        routes.append({"name": m(route, "name"),
                       "service": (spec.get("to") or {}).get("name", ""),
                       "tls": tls.get("termination", "none")})
    # Metadata-only, explicit network policies; never infer actual enforced flows
    # from policy counts alone (CNI behavior and selectors are not tested here).
    network_policy_summaries = []
    for np in lists["networkpolicies"]:
        spec = np.get("spec", {})
        network_policy_summaries.append({
            "name": m(np, "name"),
            "types": spec.get("policyTypes", []),
            "ingress_rules": len(spec.get("ingress") or []),
            "egress_rules": len(spec.get("egress") or []),
            "pod_selector_labels": sorted((spec.get("podSelector") or {}).get("matchLabels", {}).keys())
        })
    consumers = []
    svc_map = {s["name"]: s["workload_candidates"] for s in services}
    for w in lists["deployments"] + lists["statefulsets"] + lists["daemonsets"]:
        for c in w.get("spec", {}).get("template", {}).get("spec", {}).get("containers", []):
            for env in c.get("env", []) or []:
                host = safe_host_env(env)
                if host:
                    # Accept single namespace and service FQDN within same namespace.
                    short = host.split(".")[0]
                    if "." in host and host not in (f"{short}.{ns}", f"{short}.{ns}.svc", f"{short}.{ns}.svc.cluster.local"):
                        target = []
                    else:
                        target = svc_map.get(short, [])
                    consumers.append({"application": m(w, "name"), "env_key": env.get("name"),
                                      "service_candidate": short if target else "UNRESOLVED",
                                      "workloads_by_selector": target,
                                      "proof": "ENV_HOST_AND_SVC_SELECTOR_ONLY_NOT_SQL" if target else "UNRESOLVED"})
    events = [dict(type=e.get("type", ""), reason=e.get("reason", ""), kind=e.get("involvedObject", {}).get("kind", ""))
              for e in lists["events"] if e.get("type") == "Warning"][-30:]
    if top_expected != top_match and top_ok:
        add_finding(findings, "P2", "TOP_COVERAGE_INCOMPLETE", f"{top_match}/{top_expected} running containers matched", "oc adm top snapshot")
    argo = []
    gitops_accessible = None
    if include_gitops:
        argo_query = get_obj(GITOPS_NS, "applications.argoproj.io")
        gitops_accessible = isinstance(argo_query, dict)
        for a in (argo_query or {}).get("items", []):
            dest = a.get("spec", {}).get("destination", {})
            if dest.get("namespace") != ns:
                continue
            argo.append({"name": m(a, "name"), "sync": a.get("status", {}).get("sync", {}).get("status", "UNKNOWN"),
                         "health": a.get("status", {}).get("health", {}).get("status", "UNKNOWN"),
                         "automated": bool(a.get("spec", {}).get("syncPolicy", {}).get("automated")),
                         "target_revision": a.get("spec", {}).get("source", {}).get("targetRevision", "UNKNOWN"),
                         "conditions": sorted({c.get("type", "UNKNOWN") for c in a.get("status", {}).get("conditions", [])})})
            if argo[-1]["sync"] in ("Unknown", "OutOfSync"):
                add_finding(findings, "P1", "GITOPS_NOT_SYNCED", f"Application/{m(a, 'name')} status={argo[-1]['sync']}", "ArgoCD.status.sync")
    counts = {key: len(items) for key, items in lists.items() if key != "events"}
    counts["warning_events"] = len(events)
    report = {
        "namespace": ns, "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "read-only oc get + optional oc adm top; no resource modifications",
        "counts": counts,
        "workloads": workloads, "pvc": pvcs, "services": services, "routes": routes,
        "network_policy_summaries": network_policy_summaries,
        "db_consumer_candidates": consumers, "gitops": argo, "gitops_api_accessible": gitops_accessible,
        "warnings_last_30": events, "unavailable_or_forbidden_resources": unavailable,
        "sample": {"top_available": bool(top_ok and top), "cpu_req_m_active_containers": round(total_cpu_req, 3),
                   "ram_req_mi_active_containers": round(total_mem_req, 3),
                   "cpu_top_m_matched_only": round(total_cpu_obs, 3) if top_ok and top else None,
                   "ram_top_mi_matched_only": round(total_mem_obs, 3) if top_ok and top else None,
                   "top_container_match": f"{top_match}/{top_expected}",
                   "note": "Single sample; not P95/CO2, missing metrics are not zero usage"},
        "source_code": local_repo(repo_path),
        "findings": sorted(findings, key=lambda f: {"P0": 0, "P1": 1, "P2": 2, "INFO": 3}[f["severity"]]),
        "limitations": ["No database connections/queries or logical DB counts measured",
                        "No Secrets/ConfigMap values read or stored",
                        "Storage capacity != actual used bytes; no backup restore attempted",
                        "No energy meter or calibrated carbon footprint; no CO2 estimate",
                        "Security checks are workload metadata heuristics, not penetration testing",
                        "No scalability/load/SLO/P95 evidence from single top sample",
                        "Only deployment/statefulset/daemonset pod requests modeled; not all job/system pods"],
    }
    return report


def markdown(rep):
    lines = [f"# Audit OpenShift/CRC — {rep['namespace']}", "", f"Capture UTC: {rep['generated_at_utc']}",
             "", "## Synthèse", "",
             f"- Workloads déclarés (Deployments + StatefulSets + DaemonSets): **{len(rep['workloads'])}**",
             f"- Pods: **{rep['counts']['pods']}** ; PVC: **{rep['counts']['pvc']}** ; Services: **{rep['counts']['services']}**",
             f"- CPU demandé pour les conteneurs actifs recensés: **{rep['sample']['cpu_req_m_active_containers']}m**",
             f"- RAM demandée pour les conteneurs actifs recensés: **{rep['sample']['ram_req_mi_active_containers']} MiB**",
             f"- CPU observé (échantillon): **{rep['sample']['cpu_top_m_matched_only']}m** ; RAM observée: **{rep['sample']['ram_top_mi_matched_only']} MiB**",
             f"- Couverture oc top: **{rep['sample']['top_container_match']}**", "",
             "## Workloads", "", "| Type | Nom | Ready / Desired | Image(s) | emptyDir | PVC |", "|---|---|---:|---|---|---|"]
    def cell(x): return str(x).replace("|", "/").replace("\n", " ")
    for w in rep["workloads"]:
        lines.append(f"| {w['kind']} | {cell(w['name'])} | {w['ready']}/{w['desired']} | {cell(', '.join(w['images']))} | {cell(', '.join(w['emptydir_mounts']) or '—')} | {cell(', '.join(w['pvc_claims']) or '—')} |")
    lines += ["", "## Stockage", "", "| PVC | Bound | Demande | PV reclaim | Occupation réelle |", "|---|---|---|---|---|"]
    for p in rep["pvc"]:
        lines.append(f"| {cell(p['name'])} | {cell(p['phase'])} | {cell(p['requested'])} | {cell(p['reclaim'])} | NON MESURÉE |")
    lines += ["", "## GitOps", ""]
    if rep["gitops"]:
        for x in rep["gitops"]:
            lines.append(f"- {cell(x['name'])}: sync={x['sync']}, health={x['health']}, auto={x['automated']}, conditions={', '.join(x['conditions']) or 'none'}")
    else:
        lines.append("Non démontré, accès API Argo CD indisponible, ou aucune Application correspondante visible." if rep["gitops_api_accessible"] is not True else "Aucune Application Argo CD correspondante dans le namespace interrogé.")
    lines += ["", "## Connexions candidates (configuration seulement)", "",
              f"- Liens identifiés: {len(rep['db_consumer_candidates'])}; **pas** des connexions SQL prouvées."]
    for x in rep["db_consumer_candidates"]:
        lines.append(f"- {cell(x['application'])} -> {cell(x['service_candidate'])} ({cell(x['env_key'])}); {cell(x['proof'])}")
    lines += ["", "## Constats par priorité", ""]
    for f in rep["findings"]:
        lines.append(f"- **{f['severity']} · {f['code']}** — {cell(f['detail'])} (preuve: {cell(f['evidence'])})")
    lines += ["", "## Limites et actions interdites", ""]
    lines += [f"- {s}" for s in rep["limitations"]]
    lines += ["- Aucune modification Kubernetes, redémarrage, export de Secrets ou requête SQL n'est réalisée.", "",
              "## Ressources inaccessibles ou non installées", "", ", ".join(rep["unavailable_or_forbidden_resources"]) or "Aucune dans le périmètre testé."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--namespace", "-n", action="append", required=True, help="Namespace à auditer; répéter l'option pour un projet multi-namespace")
    ap.add_argument("--repo-root", help="Dépôt Git local optionnel (inventaire statique des fichiers sans lecture de contenu)")
    ap.add_argument("--output-dir", help="Par défaut : evidence/local/private-openshift-audit-<UTC>")
    ap.add_argument("--no-gitops", action="store_true", help="Ne pas chercher Argo CD dans openshift-gitops")
    opt = ap.parse_args(argv)
    namespaces = list(dict.fromkeys(opt.namespace))
    for ns in namespaces:
        if len(ns) > 63 or not SAFE_NS.fullmatch(ns):
            ap.error(f"Nom de namespace invalide : {ns}")
    root = Path(opt.output_dir or ("evidence/local/private-openshift-audit-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")))
    # Fail closed: no accidental public artifact in repository or arbitrary directory.
    normalized = str(root).replace("\\", "/")
    if not normalized.startswith("evidence/local/private-"):
        ap.error("Le dossier de sortie doit être dans evidence/local/private-* (gitignored)")
    ok, _ = run(["oc", "whoami"])
    if not ok:
        ap.error("Connexion oc absente; faire oc login avant l'audit")
    root.mkdir(parents=True, exist_ok=False)
    summary = []
    for ns in namespaces:
        try:
            rep = analyze_namespace(ns, opt.repo_root, not opt.no_gitops)
        except RuntimeError as exc:
            summary.append(f"{ns}: ERROR={exc}")
            continue
        (root / f"{ns}.report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (root / f"{ns}.report.md").write_text(markdown(rep), encoding="utf-8")
        # Offline HTML contains inline CSS/SVG; no additional oc calls or network.
        from render_openshift_project_html import render_html
        (root / f"{ns}.report.html").write_text(render_html(rep), encoding="utf-8")
        p0 = sum(f["severity"] == "P0" for f in rep["findings"])
        p1 = sum(f["severity"] == "P1" for f in rep["findings"])
        summary.append(f"NAMESPACE={ns} WORKLOADS={len(rep['workloads'])} PODS={rep['counts']['pods']} PVCS={rep['counts']['pvc']} P0={p0} P1={p1} TOP_COVERAGE={rep['sample']['top_container_match']}")
    summary.extend(["HTML_REPORT_PER_NAMESPACE=true", "HTML_NO_EXTERNAL_ASSETS=true", "POSTURE=READ_ONLY", "NO_SECRET_VALUES_STORED=true", "NO_SQL_OR_POD_RESTART=true", "NO_CALIBRATED_CO2_ESTIMATE=true",
                    "RESULTS_ARE_LOCAL_PRIVATE_AND_SINGLE_TIMEPOINT=true", f"EVIDENCE_DIR={root}"])
    (root / "SUMMARY.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    return 0 if len([line for line in summary if "ERROR=" in line]) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
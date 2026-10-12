#!/usr/bin/env python3
"""CRC safe PARK/RESUME for Trading, Decision API, and API Management only.

No StatefulSet/PVC/Secret modifications. One state file per project kept outside Git.
GitOps automated policy and CronJob suspend values are snapshotted and restored.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

PROJECTS = {
    "trading": {"namespace": "trading-perso", "deployments": ("rapport-horaire",)},
    "decision": {"namespace": "mayainsurance-decision-local", "deployments": ("decision-api",)},
    "api": {"namespace": "mayabank-api", "deployments": ("api-gateway", "payment-api")},
}
GITOPS_NS = "openshift-gitops"
ROOT = Path(os.environ.get("CRC_EXTRA_STATE_DIR", str(Path.home() / ".crc-capacity")))


def oc(*args: str) -> dict | str:
    proc = subprocess.run(["oc", "--request-timeout=25s", *args], capture_output=True,
                          text=True, check=False, timeout=70)
    if proc.returncode:
        raise RuntimeError("oc " + " ".join(args[:4]) + ": " + proc.stderr[:180])
    if len(args) >= 2 and args[-2:] == ("-o", "json"):
        return json.loads(proc.stdout)
    return proc.stdout.strip()


def get(ns: str, kind: str, name: str) -> dict:
    return oc("-n", ns, "get", kind, name, "-o", "json")


def ls(ns: str, kind: str) -> list[dict]:
    out = oc("-n", ns, "get", kind, "-o", "json")
    if not isinstance(out, dict) or not isinstance(out.get("items"), list):
        raise RuntimeError("INVALID_RESOURCE_LIST")
    return out["items"]


def snapshot_path(project: str) -> Path:
    return ROOT / ("crc-" + project + ".json")


def state_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def state_read(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError("NO_SNAPSHOT_AT=" + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def check_crc() -> None:
    out = oc("get", "nodes", "-o", "json")
    nodes = out["items"]
    if [n["metadata"]["name"] for n in nodes] != ["crc"]:
        raise RuntimeError("EXPECTED_SINGLE_CRC_NODE")
    if not any(c["type"] == "Ready" and c["status"] == "True"
               for c in nodes[0]["status"]["conditions"]):
        raise RuntimeError("CRC_NODE_NOT_READY")


def inspect(project: str) -> dict:
    check_crc()
    cfg = PROJECTS[project]
    ns = cfg["namespace"]
    all_deps = {d["metadata"]["name"]: d for d in ls(ns, "deployments")}
    if set(all_deps) != set(cfg["deployments"]):
        raise RuntimeError("DEPLOYMENT_SET_CHANGED:" + ns + ":" + ",".join(sorted(all_deps)))
    hpas = ls(ns, "hpa")
    if hpas:
        raise RuntimeError("HPA_PRESENT:" + ns)
    if any((job.get("status") or {}).get("active", 0) > 0 for job in ls(ns, "jobs")):
        raise RuntimeError("ACTIVE_JOB_PRESENT:" + ns)
    if ls(ns, "statefulsets"):
        raise RuntimeError("UNEXPECTED_STATEFULSET:" + ns)
    if ls(ns, "pvc"):
        raise RuntimeError("UNEXPECTED_PVC:" + ns)
    deployments = []
    for name in cfg["deployments"]:
        d = all_deps[name]
        template = ((d.get("spec") or {}).get("template") or {}).get("spec") or {}
        if any(any(k in v for k in ("emptyDir", "persistentVolumeClaim", "hostPath", "ephemeral", "csi"))
               for v in template.get("volumes") or []):
            raise RuntimeError("UNSAFE_VOLUME:" + ns + "/" + name)
        if d["metadata"].get("deletionTimestamp"):
            raise RuntimeError("TERMINATING_DEPLOYMENT:" + name)
        replicas = d.get("spec", {}).get("replicas", 1)
        if not isinstance(replicas, int) or replicas < 0:
            raise RuntimeError("INVALID_REPLICA_COUNT:" + name)
        deployments.append({"name": name, "uid": d["metadata"]["uid"], "replicas": replicas})
    cronjobs = []
    for cj in ls(ns, "cronjobs"):
        if project != "trading":
            raise RuntimeError("UNEXPECTED_CRONJOB:" + ns)
        cronjobs.append({"name": cj["metadata"]["name"], "uid": cj["metadata"]["uid"],
                         "suspend": (cj.get("spec") or {}).get("suspend")})
    apps = []
    for app in ls(GITOPS_NS, "applications.argoproj.io"):
        spec = app.get("spec") or {}
        if (spec.get("destination") or {}).get("namespace") != ns:
            continue
        auto = (spec.get("syncPolicy") or {}).get("automated")
        if any(o.get("kind") == "ApplicationSet" for o in app.get("metadata", {}).get("ownerReferences") or []):
            raise RuntimeError("ARGO_APPLICATIONSET_OWNED:" + app["metadata"]["name"])
        apps.append({"name": app["metadata"]["name"], "uid": app["metadata"]["uid"],
                     "automated": auto})
    if project == "decision" and not any(a["automated"] is not None for a in apps):
        raise RuntimeError("EXPECTED_DECISION_ARGO_AUTOSYNC_MISSING")
    return {"project": project, "namespace": ns, "deployments": deployments,
            "cronjobs": cronjobs, "applications": apps}


def patch(ns: str, kind: str, name: str, data: dict) -> None:
    oc("-n", ns, "patch", kind, name, "--type=merge", "-p", json.dumps(data))


def patch_app(name: str, automated: object) -> None:
    patch(GITOPS_NS, "application", name, {"spec": {"syncPolicy": {"automated": automated}}})
    d = get(GITOPS_NS, "application", name)
    if (d["spec"].get("syncPolicy") or {}).get("automated") != automated:
        raise RuntimeError("ARGO_PATCH_NOT_VERIFIED:" + name)


def patch_cj(ns: str, name: str, suspend: object) -> None:
    patch(ns, "cronjob", name, {"spec": {"suspend": suspend}})
    d = get(ns, "cronjob", name)
    if d["spec"].get("suspend") != suspend:
        raise RuntimeError("CRON_PATCH_NOT_VERIFIED:" + name)


def scale(ns: str, name: str, replicas: int) -> None:
    oc("-n", ns, "scale", "deployment/" + name, "--replicas=" + str(replicas))
    d = get(ns, "deployment", name)
    if d["spec"].get("replicas", 1) != replicas:
        raise RuntimeError("SCALE_NOT_VERIFIED:" + name)


def check_uids(state: dict) -> None:
    ns = state["namespace"]
    for dep in state["deployments"]:
        if get(ns, "deployment", dep["name"])["metadata"]["uid"] != dep["uid"]:
            raise RuntimeError("DEPLOYMENT_REPLACED:" + dep["name"])
    for cj in state["cronjobs"]:
        if get(ns, "cronjob", cj["name"])["metadata"]["uid"] != cj["uid"]:
            raise RuntimeError("CRONJOB_REPLACED:" + cj["name"])
    for app in state["applications"]:
        if get(GITOPS_NS, "application", app["name"])["metadata"]["uid"] != app["uid"]:
            raise RuntimeError("ARGO_APPLICATION_REPLACED:" + app["name"])


def restore(state: dict) -> None:
    check_crc()
    check_uids(state)
    ns = state["namespace"]
    for d in state["deployments"]:
        scale(ns, d["name"], d["replicas"])
    for c in state["cronjobs"]:
        patch_cj(ns, c["name"], c["suspend"])
    for a in state["applications"]:
        live = (get(GITOPS_NS, "application", a["name"])["spec"].get("syncPolicy") or {}).get("automated")
        if live is None:
            if a["automated"] is not None:
                patch_app(a["name"], a["automated"])
        elif live != a["automated"]:
            raise RuntimeError("ARGO_POLICY_DRIFT:" + a["name"])


def plan(project: str) -> None:
    state = inspect(project)
    path = snapshot_path(project)
    print("MODE=PLAN_READ_ONLY")
    print("PROJECT=" + project)
    print("NAMESPACE=" + state["namespace"])
    print("DEPLOYMENTS=" + ",".join(d["name"] + ":" + str(d["replicas"]) + "->0" for d in state["deployments"]))
    print("CRONJOBS=" + (",".join(c["name"] for c in state["cronjobs"]) or "NONE"))
    print("ARGO_TO_PAUSE=" + (",".join(a["name"] for a in state["applications"] if a["automated"] is not None) or "NONE"))
    print("SNAPSHOT=" + (state_read(path)["status"] if path.exists() else "NONE"))
    print("SAFE_DATASTORES_UNTOUCHED=true")
    print("PARK_EXECUTED=false")


def park(project: str) -> None:
    if os.environ.get("CRC_EXTRA_PARK") != "YES" or os.environ.get("CRC_EXTRA_ACK_DOWNTIME") != "YES":
        raise RuntimeError("PARK_REQUIRES_EXPLICIT_ACKS")
    path = snapshot_path(project)
    if path.exists() and state_read(path).get("status") != "RESUMED":
        raise RuntimeError("EXISTING_ACTIVE_SNAPSHOT:" + str(path))
    state = inspect(project)
    if not any(d["replicas"] > 0 for d in state["deployments"]) and not any(
            c["suspend"] is not True for c in state["cronjobs"]):
        raise RuntimeError("NOTHING_ACTIVE_TO_PARK")
    state["status"] = "PARKING"
    state["captured_at_utc"] = datetime.now(timezone.utc).isoformat()
    state_write(path, state)
    try:
        for a in state["applications"]:
            if a["automated"] is not None:
                patch_app(a["name"], None)
        for c in state["cronjobs"]:
            if c["suspend"] is not True:
                patch_cj(state["namespace"], c["name"], True)
        for d in state["deployments"]:
            if d["replicas"] > 0:
                scale(state["namespace"], d["name"], 0)
        state["status"] = "PARKED"
        state_write(path, state)
    except Exception:
        print("PARK_FAILED_ROLLBACK_ATTEMPTED", file=sys.stderr)
        try:
            restore(state)
            state["status"] = "RESUMED"
            state_write(path, state)
        except Exception as e:
            print("MANUAL_RECOVERY_REQUIRED=" + str(e)[:240], file=sys.stderr)
        raise
    print("PARK_RESULT=PASS")
    print("PROJECT=" + project)
    print("PARKED_DEPLOYMENTS=" + str(sum(d["replicas"] > 0 for d in state["deployments"])))
    print("SUSPENDED_CRONJOBS=" + str(len(state["cronjobs"])))
    print("SNAPSHOT=" + str(path))


def resume(project: str) -> None:
    if os.environ.get("CRC_EXTRA_RESUME") != "YES":
        raise RuntimeError("RESUME_REQUIRES_EXPLICIT_ACK")
    path = snapshot_path(project)
    state = state_read(path)
    if state["project"] != project or state["namespace"] != PROJECTS[project]["namespace"]:
        raise RuntimeError("SNAPSHOT_SCOPE_MISMATCH")
    if state["status"] == "RESUMED":
        print("RESUME_ALREADY_COMPLETE=true")
        return
    if state["status"] not in ("PARKING", "PARKED"):
        raise RuntimeError("UNEXPECTED_SNAPSHOT_STATUS")
    restore(state)
    state["status"] = "RESUMED"
    state_write(path, state)
    print("RESUME_RESULT=PASS")
    print("PROJECT=" + project)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "park", "resume"))
    parser.add_argument("--project", choices=PROJECTS, required=True)
    args = parser.parse_args()
    try:
        {"plan": plan, "park": park, "resume": resume}[args.mode](args.project)
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("CRC_EXTRA_ERROR=" + str(exc)[:380], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

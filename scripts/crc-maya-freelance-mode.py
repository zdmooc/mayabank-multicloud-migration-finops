#!/usr/bin/env python3
"""Maya Freelance CRC reversible dashboard/n8n PARK; PostgreSQL and PVC never scaled.

Read-only by default: plan. PARK requires explicit downtime and ephemeral-home
acknowledgements. Data volumes, Secrets, PV/PVC and database are NEVER altered.
All Kubernetes reads and writes use oc in current context without shell.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

NAMESPACE = "maya-freelance"
GITOPS_NAMESPACE = "openshift-gitops"
TARGETS = ("n8n", "maya-dashboard")
STATE = Path(os.environ.get(
    "CRC_MAYA_STATE_FILE",
    str(Path.home() / ".crc-capacity" / "maya-freelance.json"),
))
DB_IMAGES = re.compile(r"postgres|mysql|mongo|redis|kafka|rabbitmq|ibm[-/]?mq|redpanda", re.I)


def oc(*args: str, json_result: bool = False) -> object:
    p = subprocess.run(
        ["oc", "--request-timeout=25s", *args],
        text=True, capture_output=True, check=False, timeout=80,
    )
    if p.returncode:
        raise RuntimeError(f"oc {' '.join(args[:4])}: {p.stderr[:180].strip()}")
    return json.loads(p.stdout) if json_result else p.stdout.strip()


def list_items(resource: str, namespace: str) -> list[dict]:
    data = oc("-n", namespace, "get", resource, "-o", "json", json_result=True)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise RuntimeError("INVALID_K8S_LIST")
    return data["items"]


def stateless_deployment(d: dict) -> bool:
    spec = ((d.get("spec") or {}).get("template") or {}).get("spec") or {}
    containers = (spec.get("containers") or []) + (spec.get("initContainers") or [])
    if not spec.get("containers") or d.get("metadata", {}).get("deletionTimestamp"):
        return False
    if any(DB_IMAGES.search(c.get("image") or "") for c in containers):
        return False
    # Reject all PV/PVC, CSI, emptyDir, hostpath or projected data volumes.
    # These dashboard/n8n manifests should have zero pod volumes.
    if spec.get("volumes"):
        return False
    return True


def preflight() -> tuple[list[dict], list[dict]]:
    nodes = oc("get", "nodes", "-o", "json", json_result=True).get("items", [])
    if [n.get("metadata", {}).get("name") for n in nodes] != ["crc"]:
        raise RuntimeError("NOT_SINGLE_CRC_NODE")
    if not any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in nodes[0].get("status", {}).get("conditions", [])):
        raise RuntimeError("CRC_NODE_NOT_READY")
    deployments = {d["metadata"]["name"]: d for d in list_items("deployments", NAMESPACE)}
    database = deployments.get("postgres")
    if database is None:
        raise RuntimeError("POSTGRES_DEPLOYMENT_MISSING")
    db_volumes = (((database.get("spec") or {}).get("template") or {}).get("spec") or {}).get("volumes") or []
    if not any((v.get("persistentVolumeClaim") or {}).get("claimName") == "postgres-data"
               for v in db_volumes):
        raise RuntimeError("POSTGRES_PVC_REFERENCE_UNVERIFIED")
    pvc = oc("-n", NAMESPACE, "get", "pvc", "postgres-data", "-o", "json", json_result=True)
    if (pvc.get("status") or {}).get("phase") != "Bound":
        raise RuntimeError("POSTGRES_PVC_NOT_BOUND")
    hpas = list_items("hpa", NAMESPACE)
    hpa_names = {(h.get("spec", {}).get("scaleTargetRef") or {}).get("name")
                 for h in hpas if (h.get("spec", {}).get("scaleTargetRef") or {}).get("kind", "").lower() == "deployment"}
    selected = []
    for name in TARGETS:
        d = deployments.get(name)
        if d is None:
            raise RuntimeError("EXPECTED_DEPLOYMENT_MISSING:" + name)
        if name in hpa_names or not stateless_deployment(d):
            raise RuntimeError("UNSAFE_DEPLOYMENT:" + name)
        replicas = (d.get("spec") or {}).get("replicas", 1)
        if not isinstance(replicas, int) or replicas <= 0:
            raise RuntimeError("TARGET_NOT_RUNNING:" + name)
        if name == "n8n":
            env = (((d.get("spec") or {}).get("template") or {}).get("spec") or {}).get("containers", [{}])[0].get("env") or []
            encryption = [e for e in env if e.get("name") == "N8N_ENCRYPTION_KEY"]
            if len(encryption) != 1 or not (encryption[0].get("valueFrom") or {}).get("secretKeyRef"):
                raise RuntimeError("N8N_SECRET_REFERENCE_NOT_PROVEN")
        selected.append({"name": name, "replicas": replicas, "uid": d["metadata"]["uid"]})
    applications = []
    for app in list_items("applications.argoproj.io", GITOPS_NAMESPACE):
        meta = app.get("metadata") or {}
        spec = app.get("spec") or {}
        if (spec.get("destination") or {}).get("namespace") != NAMESPACE:
            continue
        automated = (spec.get("syncPolicy") or {}).get("automated")
        if automated is None:
            continue
        if any(o.get("kind") == "ApplicationSet" for o in meta.get("ownerReferences") or []):
            raise RuntimeError("ARGO_APPLICATIONSET_OWNED")
        applications.append({"name": meta["name"], "uid": meta.get("uid"), "automated": automated})
    return selected, applications


def save(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, STATE)


def read_state() -> dict:
    if not STATE.is_file():
        raise RuntimeError("NO_PREVIOUS_PARK_SNAPSHOT")
    return json.loads(STATE.read_text(encoding="utf-8"))


def app_auto(name: str) -> object:
    a = oc("-n", GITOPS_NAMESPACE, "get", "application", name, "-o", "json", json_result=True)
    return (a.get("spec", {}).get("syncPolicy") or {}).get("automated")


def change_auto(name: str, value: object) -> None:
    oc("-n", GITOPS_NAMESPACE, "patch", "application", name,
       "--type=merge", "-p", json.dumps({"spec": {"syncPolicy": {"automated": value}}}))
    if app_auto(name) != value:
        raise RuntimeError("ARGO_POLICY_NOT_VERIFIED:" + name)


def scale(name: str, replicas: int) -> None:
    oc("-n", NAMESPACE, "scale", "deployment/" + name, "--replicas=" + str(replicas))
    d = oc("-n", NAMESPACE, "get", "deployment", name, "-o", "json", json_result=True)
    if (d.get("spec") or {}).get("replicas") != replicas:
        raise RuntimeError("SCALE_NOT_VERIFIED:" + name)


def restore(state: dict) -> None:
    if state.get("namespace") != NAMESPACE:
        raise RuntimeError("SNAPSHOT_NAMESPACE_MISMATCH")
    for d in state.get("deployments") or []:
        live = oc("-n", NAMESPACE, "get", "deployment", d["name"], "-o", "json", json_result=True)
        if live.get("metadata", {}).get("uid") != d["uid"]:
            raise RuntimeError("DEPLOYMENT_IDENTITY_CHANGED:" + d["name"])
    for d in state["deployments"]:
        scale(d["name"], d["replicas"])
    for a in state["applications"]:
        current = app_auto(a["name"])
        if current is None:
            change_auto(a["name"], a["automated"])
        elif current != a["automated"]:
            raise RuntimeError("ARGO_POLICY_DRIFT:" + a["name"])
    state["status"] = "RESUMED"
    save(state)


def plan() -> None:
    selected, apps = preflight()
    print("MODE=PLAN_READ_ONLY")
    print("NAMESPACE=" + NAMESPACE)
    print("DEPLOYMENTS_TO_PARK=" + ",".join(d["name"] + ":" + str(d["replicas"]) + "->0" for d in selected))
    print("ARGO_APPS_TO_PAUSE=" + (",".join(a["name"] for a in apps) if apps else "NONE"))
    print("POSTGRES_DEPLOYMENT_AND_PVC_PROTECTED=true")
    print("N8N_WORKFLOWS_MUST_BE_QUIESCED_BEFORE_PARK=true")
    print("EXISTING_SNAPSHOT=" + (str(STATE) if STATE.exists() else "NONE"))
    print("PARK_AUTHORIZATION=NOT_GIVEN_BY_PLAN")


def park() -> None:
    if any(os.environ.get(k) != "YES" for k in (
        "CRC_MAYA_PARK",
        "CRC_MAYA_ACK_N8N_DOWNTIME",
        "CRC_MAYA_ACK_EPHEMERAL_HOME_LOSS",
        "CRC_MAYA_ACK_WORKFLOWS_QUIESCED",
    )):
        raise RuntimeError("PARK_REQUIRES_FOUR_ACKNOWLEDGEMENTS")
    if STATE.exists() and read_state().get("status") != "RESUMED":
        raise RuntimeError("PARK_SNAPSHOT_ALREADY_ACTIVE")
    selected, apps = preflight()
    if {d["name"] for d in selected} != set(TARGETS):
        raise RuntimeError("MAYA_SCOPE_NOT_EXACT")
    state = {"status": "PARKING", "namespace": NAMESPACE,
             "captured_at_utc": datetime.now(timezone.utc).isoformat(),
             "deployments": selected, "applications": apps}
    save(state)
    try:
        for app in apps:
            change_auto(app["name"], None)
        for d in selected:
            scale(d["name"], 0)
        state["status"] = "PARKED"
        save(state)
        print("PARK_RESULT=PASS")
        print("PARKED_DEPLOYMENTS=2")
        print("DATABASE_AND_PVC_UNCHANGED=true")
        print("SNAPSHOT=" + str(STATE))
    except Exception:
        print("PARK_ERROR_ATTEMPTING_ROLLBACK", file=sys.stderr)
        try:
            restore(state)
        except Exception:
            print("ROLLBACK_NEEDS_MANUAL_REVIEW=true", file=sys.stderr)
        raise


def resume() -> None:
    if os.environ.get("CRC_MAYA_RESUME") != "YES":
        raise RuntimeError("RESUME_REQUIRES_CRC_MAYA_RESUME=YES")
    state = read_state()
    if state["status"] == "RESUMED":
        print("RESUME_ALREADY_COMPLETE=true")
        return
    if state["status"] not in ("PARKING", "PARKED"):
        raise RuntimeError("INVALID_SNAPSHOT_STATUS")
    restore(state)
    print("RESUME_RESULT=PASS")
    print("RESTORED_DEPLOYMENTS=2")
    print("POSTGRES_AND_PVC_UNCHANGED=true")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode", choices=("plan", "park", "resume"))
    args = ap.parse_args()
    try:
        if args.mode == "plan":
            plan()
        elif args.mode == "park":
            park()
        else:
            resume()
        return 0
    except (RuntimeError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as exc:
        print("CRC_MAYA_ERROR=" + str(exc)[:250], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

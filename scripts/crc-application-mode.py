#!/usr/bin/env python3
"""CRC Instant Payments stateless-app PARK / RESUME with GitOps pause and rollback.

Default is PLAN ONLY. PARK requires CRC_CAPACITY_PARK=YES.
RESUME requires CRC_CAPACITY_RESUME=YES.
Protected: database/Kafka/stateful workloads, PVC, pods, secrets, namespace.
Do not use for OpenShift system namespaces or for production clusters.
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

NS = "instant-payments-local"
APPS_NS = "openshift-gitops"
# Only already-known business/UI apps; never DB, Kafka, platform or observability.
TARGETS = (
    "payment-orchestrator", "reconciliation-service",
    "acceptor-service", "consumer-psp", "payment-read-model",
    "integration-camel", "demo-cockpit", "dependency-simulator", "wero-ui",
)
STATE = Path(os.environ.get(
    "CRC_CAPACITY_STATE_FILE",
    str(Path.home() / ".crc-capacity" / "instant-payments-local.json"),
))
STATEFUL_IMAGE = re.compile(
    r"postgres|mysql|mariadb|mongo|redis|kafka|redpanda|rabbitmq|"
    r"ibm[-/]?mq|zookeeper|cassandra|qdrant|etcd|elastic|opensearch",
    re.I,
)


def oc(*args: str, json_result: bool = False) -> dict | str:
    # No shell, no exec, no log/Secret content read.
    p = subprocess.run(
        ["oc", "--request-timeout=25s", *args],
        text=True, capture_output=True, check=False, timeout=80,
    )
    if p.returncode:
        raise RuntimeError(f"oc {' '.join(args[:4])}: {p.stderr[:240].strip()}")
    if json_result:
        value = json.loads(p.stdout)
        if not isinstance(value, dict):
            raise RuntimeError("invalid JSON document")
        return value
    return p.stdout.strip()


def items(resource: str, ns: str) -> list[dict]:
    data = oc("-n", ns, "get", resource, "-o", "json", json_result=True)
    return data.get("items", [])


def is_stateless(item: dict) -> tuple[bool, str]:
    spec = (((item.get("spec") or {}).get("template") or {}).get("spec") or {})
    volumes = spec.get("volumes") or []
    for v in volumes:
        if any(key in v for key in ("emptyDir", "persistentVolumeClaim", "hostPath", "ephemeral", "csi")):
            return False, "DATA_OR_EPHEMERAL_VOLUME"
    for c in (spec.get("containers") or []) + (spec.get("initContainers") or []):
        if STATEFUL_IMAGE.search(c.get("image") or ""):
            return False, "STATEFUL_CONTAINER_IMAGE"
    if item.get("metadata", {}).get("deletionTimestamp"):
        return False, "TERMINATING"
    if not spec.get("containers"):
        return False, "NO_CONTAINERS"
    return True, "STATELESS_TEMPLATE"


def inspect() -> tuple[list[dict], list[dict], list[str]]:
    node = oc("get", "nodes", "-o", "json", json_result=True)
    names = [n.get("metadata", {}).get("name", "") for n in node.get("items", [])]
    if names != ["crc"]:
        raise RuntimeError(f"EXPECTED_SINGLE_CRC_NODE_FOUND={names}")
    if not any(c.get("type") == "Ready" and c.get("status") == "True"
               for c in node["items"][0].get("status", {}).get("conditions", [])):
        raise RuntimeError("CRC_NODE_NOT_READY")

    depl = {x.get("metadata", {}).get("name"): x for x in items("deployments", NS)}
    hpa = items("hpa", NS)
    hpa_targets = {
        (x.get("spec", {}).get("scaleTargetRef") or {}).get("name")
        for x in hpa
        if (x.get("spec", {}).get("scaleTargetRef") or {}).get("kind", "").lower() == "deployment"
    }

    selected, blocked = [], []
    for name in TARGETS:
        x = depl.get(name)
        if not x:
            blocked.append(f"{name}:ABSENT")
            continue
        allowed, why = is_stateless(x)
        if not allowed or name in hpa_targets:
            blocked.append(f"{name}:{'HPA_CONTROLLED' if name in hpa_targets else why}")
            continue
        replicas = x.get("spec", {}).get("replicas", 1)
        if not isinstance(replicas, int) or replicas < 0:
            blocked.append(f"{name}:INVALID_REPLICAS")
            continue
        if replicas > 0:
            selected.append({"name": name, "replicas": replicas,
                             "uid": x["metadata"]["uid"]})

    applications = []
    for app in items("applications.argoproj.io", APPS_NS):
        spec = app.get("spec") or {}
        dest = spec.get("destination") or {}
        if dest.get("namespace") != NS:
            continue
        meta = app.get("metadata") or {}
        policy = spec.get("syncPolicy") or {}
        automatic = policy.get("automated")
        if automatic is not None and any(
            owner.get("kind") == "ApplicationSet"
            for owner in meta.get("ownerReferences") or []
        ):
            blocked.append(f"ARGO_APPLICATIONSET_OWNED:{meta.get('name')}")
        if automatic is not None:
            applications.append({
                "name": meta["name"], "automated": automatic,
                "uid": meta.get("uid"),
            })
    if not applications:
        # Known D-091 GitOps-managed CRC deployment; do not bypass the guard.
        blocked.append("NO_AUTOSYNC_AROGO_APPS_FOUND_VERIFY_GITOPS_OWNERS")
    return selected, applications, blocked


def write_state(data: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_name(STATE.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, STATE)


def load_state() -> dict:
    if not STATE.is_file():
        raise RuntimeError(f"NO_PARK_SNAPSHOT_AT={STATE}")
    return json.loads(STATE.read_text(encoding="utf-8"))


def app_automated(name: str) -> object:
    x = oc("-n", APPS_NS, "get", "application", name, "-o", "json", json_result=True)
    return ((x.get("spec") or {}).get("syncPolicy") or {}).get("automated")


def pause_gitops(name: str) -> None:
    oc("-n", APPS_NS, "patch", "application", name, "--type=merge",
       "-p", json.dumps({"spec": {"syncPolicy": {"automated": None}}}))
    if app_automated(name) is not None:
        raise RuntimeError(f"AUTOSYNC_STILL_ENABLED={name}")


def restore_gitops(name: str, automated: object) -> None:
    if app_automated(name) is not None:
        raise RuntimeError(f"ARGO_CHANGED_EXTERNALLY={name}")
    oc("-n", APPS_NS, "patch", "application", name, "--type=merge",
       "-p", json.dumps({"spec": {"syncPolicy": {"automated": automated}}}))


def scale(name: str, count: int) -> None:
    oc("-n", NS, "scale", "deployment/" + name, "--replicas=" + str(count))
    actual = oc("-n", NS, "get", "deployment", name,
                "-o", "json", json_result=True)
    if (actual.get("spec") or {}).get("replicas", 1) != count:
        raise RuntimeError(f"DEPLOYMENT_SCALE_MISMATCH={name}")


def park() -> None:
    if os.environ.get("CRC_CAPACITY_PARK") != "YES":
        raise RuntimeError("PARK_REQUIRES_CRC_CAPACITY_PARK=YES")
    if STATE.exists() and load_state().get("status") != "RESUMED":
        raise RuntimeError(f"EXISTING_ACTIVE_SNAPSHOT={STATE} — use resume, no overwrite")
    selected, applications, blocked = inspect()
    critical = [b for b in blocked if b.startswith(("ARGO_", "NO_AUTOSYNC_"))]
    if critical:
        raise RuntimeError("PARK_BLOCKED=" + ",".join(critical))
    if len(selected) < 2:
        raise RuntimeError("LESS_THAN_TWO_ELIGIBLE_RUNNING_DEPLOYMENTS")
    snapshot = {
        "status": "PARKING", "namespace": NS,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "deployments": selected, "applications": applications,
        "skipped": blocked,
    }
    write_state(snapshot)
    try:
        for app in applications:
            pause_gitops(app["name"])
        for d in selected:
            scale(d["name"], 0)
        snapshot["status"] = "PARKED"
        write_state(snapshot)
        print(f"PARKED_DEPLOYMENTS={len(selected)}")
        print("SKIPPED_UNSAFE_OR_ABSENT=" + (",".join(blocked) if blocked else "NONE"))
        print("PARK_RESULT=PASS")
        print(f"SNAPSHOT={STATE}")
        print("DEPENDENCY_POSTGRES_KAFKA_MQ_WAS_NOT_SCALED=true")
        print("RESUME_COMMAND=CRC_CAPACITY_RESUME=YES python scripts/crc-application-mode.py resume")
    except Exception:
        print("PARK_ERROR_ATTEMPTING_ROLLBACK", file=sys.stderr)
        try:
            resume_impl(snapshot)
        except Exception as exc:
            print(f"ROLLBACK_NEEDS_MANUAL_REVIEW={exc}", file=sys.stderr)
        raise


def resume_impl(snapshot: dict) -> None:
    if snapshot.get("namespace") != NS:
        raise RuntimeError("SNAPSHOT_NAMESPACE_MISMATCH")
    # If the attempted PARK failed before pause, app auto-sync may still be active.
    for d in snapshot["deployments"]:
        current = oc("-n", NS, "get", "deployment", d["name"],
                     "-o", "json", json_result=True)
        if current.get("metadata", {}).get("uid") != d["uid"]:
            raise RuntimeError(f"DEPLOYMENT_REPLACED={d['name']}")
    for d in snapshot["deployments"]:
        scale(d["name"], d["replicas"])
    for a in snapshot["applications"]:
        current = app_automated(a["name"])
        if current is None:
            restore_gitops(a["name"], a["automated"])
        elif current != a["automated"]:
            raise RuntimeError(f"GITOPS_POLICY_DRIFT={a['name']}")
    snapshot["status"] = "RESUMED"
    write_state(snapshot)


def resume() -> None:
    if os.environ.get("CRC_CAPACITY_RESUME") != "YES":
        raise RuntimeError("RESUME_REQUIRES_CRC_CAPACITY_RESUME=YES")
    snapshot = load_state()
    if snapshot.get("status") == "RESUMED":
        print("RESUME_ALREADY_COMPLETE=true")
        return
    if snapshot.get("status") not in ("PARKING", "PARKED"):
        raise RuntimeError("UNEXPECTED_SNAPSHOT_STATUS")
    resume_impl(snapshot)
    print("RESUME_RESULT=PASS")
    print(f"RESTORED_DEPLOYMENTS={len(snapshot['deployments'])}")


def plan() -> None:
    selected, apps, blocked = inspect()
    print("MODE=PLAN_READ_ONLY")
    print(f"TARGET_NAMESPACE={NS}")
    print("APPS_TO_PARK=" + ",".join(f"{d['name']}:{d['replicas']}->0" for d in selected))
    print("GITOPS_APPLICATIONS_TO_PAUSE=" + ",".join(a["name"] for a in apps))
    critical = [b for b in blocked if b.startswith(("ARGO_", "NO_AUTOSYNC_"))]
    skipped = [b for b in blocked if b not in critical]
    print("SKIPPED_UNSAFE_OR_ABSENT=" + (",".join(skipped) if skipped else "NONE"))
    print("BLOCKERS=" + (",".join(critical) if critical else "NONE"))
    print(f"EXISTING_SNAPSHOT={STATE if STATE.exists() else 'NONE'}")
    print("DATA_STORES_AND_PLATFORM_NOT_SCALED=true")
    print("PROJECT_PARK_AUTHORIZATION=NOT_GIVEN_BY_PLAN")
    print("NEXT=Only park when blockers NONE and operator chooses PARK with explicit confirmation.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("plan", "park", "resume"))
    args = parser.parse_args()
    try:
        if args.mode == "plan":
            plan()
        elif args.mode == "park":
            park()
        else:
            resume()
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print("CRC_CAPACITY_ERROR=" + str(exc)[:450], file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

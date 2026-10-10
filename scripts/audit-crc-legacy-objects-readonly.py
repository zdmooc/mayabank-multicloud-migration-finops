#!/usr/bin/env python3
"""Inventory non-Pod legacy candidates on OpenShift/CRC, read-only.

Collect Build, BuildConfig, ImageStream, Job, CronJob, ReplicaSet,
Deployment, PVC and Route METADATA ONLY from 'oc get ... -A -o json'.
No Secrets, no ConfigMap contents, no destructive operations.
An old or scale-zero object is NEVER automatically safe to delete.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import subprocess
import sys

RESOURCE_TYPES = (
    "builds",
    "buildconfigs",
    "imagestreams",
    "jobs",
    "cronjobs",
    "replicasets",
    "deployments",
    "pvc",
    "routes",
)
PRINT_TYPES = tuple(x for x in RESOURCE_TYPES if x != "deployments")
BUILD_TERMINAL = {"Complete", "Failed", "Error", "Cancelled"}
PROTECTED_PREFIXES = ("openshift-", "kube-")
PROTECTED_NS = {
    "instant-payments-local", "mayabank-mq-local", "tradeops",
    "maya-freelance", "keycloak-system", "shared-platform-services",
    "shared-observability", "hostpath-provisioner",
}

def run_oc(resource: str) -> list[dict]:
    cmd = ["oc", "get", resource, "-A", "-o", "json"]
    proc = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=90)
    if proc.returncode:
        raise RuntimeError(f"{resource}: {proc.stderr.strip()[:240]}")
    result = json.loads(proc.stdout)
    if not isinstance(result.get("items"), list):
        raise ValueError(f"Missing items for {resource}")
    return result["items"]

def age_days(raw: str | None, now: datetime) -> int | None:
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return max(0, (now - when).days)
    except ValueError:
        return None

def meta_id(item: dict) -> tuple[str, str]:
    metadata = item.get("metadata") or {}
    return (metadata.get("namespace") or "<unknown>", metadata.get("name") or "<unknown>")

def analysis(collections: dict[str, list[dict]], now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    summary = defaultdict(Counter)
    zero_rs = defaultdict(Counter)
    terminal_builds = defaultdict(Counter)
    rs_owner_examples = defaultdict(set)
    build_phase = defaultdict(Counter)

    # Referential lookup used ONLY to classify revision history as linked vs absent.
    deployments = {meta_id(d) for d in collections["deployments"]}
    buildconfigs = {meta_id(b) for b in collections["buildconfigs"]}

    for resource in PRINT_TYPES:
        for item in collections[resource]:
            ns, name = meta_id(item)
            summary[ns][resource] += 1

            meta = item.get("metadata") or {}
            days = age_days(meta.get("creationTimestamp"), now)
            older14 = days is not None and days >= 14

            if resource == "replicasets":
                replicas = (item.get("spec") or {}).get("replicas", 1)
                owner = next((o.get("name") for o in (meta.get("ownerReferences") or [])
                             if o.get("kind") == "Deployment"), None)
                # Both desired and observed status must be zero for zero-RS status.
                status_replicas = (item.get("status") or {}).get("replicas")
                is_zero = replicas == 0 and status_replicas == 0
                if is_zero:
                    zero_rs[ns]["zero"] += 1
                    if older14:
                        zero_rs[ns]["zero_14d"] += 1
                    if owner and (ns, owner) in deployments:
                        zero_rs[ns]["owned_by_existing_deployment"] += 1
                        rs_owner_examples[ns].add(owner)
                    elif owner:
                        zero_rs[ns]["owner_deployment_not_found"] += 1
                    else:
                        zero_rs[ns]["no_deployment_owner"] += 1
                else:
                    zero_rs[ns]["nonzero"] += 1

            elif resource == "builds":
                phase = (item.get("status") or {}).get("phase") or "Unknown"
                build_phase[ns][phase] += 1
                if phase in BUILD_TERMINAL:
                    terminal_builds[ns]["terminal"] += 1
                    if older14:
                        terminal_builds[ns]["terminal_14d"] += 1
                    config = ((meta.get("labels") or {}).get("openshift.io/build-config.name")
                              or (meta.get("annotations") or {}).get("openshift.io/build-config.name"))
                    if config and (ns, config) in buildconfigs:
                        terminal_builds[ns]["with_current_buildconfig"] += 1
                    else:
                        terminal_builds[ns]["without_matched_buildconfig"] += 1
                else:
                    terminal_builds[ns]["nonterminal"] += 1

            elif resource == "jobs":
                st = item.get("status") or {}
                terminal = bool(st.get("completionTime") or st.get("succeeded") or
                                any(c.get("type") in ("Complete", "Failed") and
                                    c.get("status") == "True"
                                    for c in st.get("conditions") or []))
                if terminal:
                    summary[ns]["jobs_terminal"] += 1
                    if older14:
                        summary[ns]["jobs_terminal_14d"] += 1

            elif resource == "cronjobs":
                if (item.get("spec") or {}).get("suspend") is True:
                    summary[ns]["cronjobs_suspended"] += 1

            elif resource == "pvc":
                phase = (item.get("status") or {}).get("phase")
                if phase == "Bound":
                    summary[ns]["pvc_bound"] += 1
                else:
                    summary[ns]["pvc_other_status"] += 1

            elif resource == "imagestreams":
                # Stream count != number/size of stored OCI images.
                tags = (item.get("status") or {}).get("tags") or []
                summary[ns]["imagestream_status_tags"] += len(tags)
                summary[ns]["imagestream_tag_events"] += sum(
                    len(x.get("items") or []) for x in tags
                )

    totals = Counter()
    for ns, row in summary.items():
        for k, v in row.items():
            totals[k] += v
    zero_total = sum(c["zero"] for c in zero_rs.values())
    build_total = sum(c["terminal"] for c in terminal_builds.values())
    return {
        "timestamp": now.isoformat(),
        "totals": totals,
        "namespaces": summary,
        "zero_rs": zero_rs,
        "terminal_builds": terminal_builds,
        "rs_owner_examples": rs_owner_examples,
        "build_phase": build_phase,
        "zero_rs_total": zero_total,
        "terminal_build_total": build_total,
    }

def show(report: dict) -> None:
    print("CRC_LEGACY_OBJECTS_AUDIT=READ_ONLY")
    print("RESOURCE_MUTATIONS=false")
    print("SECRETS_READ=false")
    print("IMAGE_BYTES_MEASURED=false")
    print("DISK_SAVINGS_ESTIMATED=false")
    print("SOURCE_DELETION_APPROVED=false")
    print(f"UTC={report['timestamp']}")
    totals = report["totals"]
    for kind in PRINT_TYPES:
        print(f"TOTAL_{kind.upper()}={totals[kind]}")
    print(f"REPLICASETS_ZERO_DESIRED_AND_OBSERVED={report['zero_rs_total']}")
    print(f"REPLICASETS_ZERO_14_DAYS_OR_OLDER={sum(c['zero_14d'] for c in report['zero_rs'].values())}")
    print(f"REPLICASETS_ZERO_WITH_EXISTING_DEPLOYMENT={sum(c['owned_by_existing_deployment'] for c in report['zero_rs'].values())}")
    print(f"REPLICASETS_ZERO_WITHOUT_FOUND_DEPLOYMENT={sum(c['no_deployment_owner'] + c['owner_deployment_not_found'] for c in report['zero_rs'].values())}")
    print(f"BUILDS_TERMINAL={report['terminal_build_total']}")
    print(f"BUILDS_TERMINAL_14_DAYS_OR_OLDER={sum(c['terminal_14d'] for c in report['terminal_builds'].values())}")
    print(f"JOBS_TERMINAL={totals['jobs_terminal']}")
    print(f"CRONJOBS_SUSPENDED={totals['cronjobs_suspended']}")
    print(f"PVCS_BOUND_PROTECTED={totals['pvc_bound']}")
    print("")
    print("=== BY NAMESPACE, DESCRIPTIVE COUNTS ONLY ===")
    print("NAMESPACE\tZERO_RS\tZERO_RS_14D\tOWNED_BY_DEPLOYMENT\tTERMINAL_BUILDS\tTERMINAL_BUILDS_14D\tIMAGESTREAMS\tBUILDCONFIGS\tJOBS\tCRONJOBS\tPVC\tROUTES\tREVIEW_SCOPE")
    ns = report["namespaces"]
    for name in sorted(ns, key=lambda n: (
            -report["zero_rs"][n]["zero"] - report["terminal_builds"][n]["terminal"], n)):
        row = ns[name]
        rs = report["zero_rs"][name]
        builds = report["terminal_builds"][name]
        protected = name.startswith(PROTECTED_PREFIXES) or name in PROTECTED_NS
        print("\t".join(map(str, [
            name, rs["zero"], rs["zero_14d"],
            rs["owned_by_existing_deployment"], builds["terminal"],
            builds["terminal_14d"], row["imagestreams"],
            row["buildconfigs"], row["jobs"], row["cronjobs"],
            row["pvc"], row["routes"], "PROTECTED" if protected else "REVIEW_ONLY"
        ])))
    print("")
    print("=== NOT AUTOMATIC CLEANUP CANDIDATES ===")
    print("ZERO_RS=Deployment revision history may be needed for rollback.")
    print("BUILDS=May be referenced by BuildConfig/ImageStream; age alone is not deletion approval.")
    print("IMAGESTREAMS=Reference/tag metadata; OCI disk consumption is NOT measured.")
    print("PVC=Never delete without verified backup and retention decision.")
    print("RESULT=INVENTORY_ONLY_REVIEW_BEFORE_ANY_CLEANUP")

def main() -> int:
    try:
        collections = {resource: run_oc(resource) for resource in RESOURCE_TYPES}
        show(analysis(collections))
        return 0
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        print(f"INVENTORY_FAILED_READONLY={str(exc)[:350]}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())

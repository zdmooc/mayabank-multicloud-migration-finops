# I1 — CRC collector execution (user-provided console evidence)

**Observation date:** 2026-10-10 (UTC 07:55:38–07:55:51). **Status:** COLLECTOR_RAN / POD_AND_PVC_FILES_WRITTEN / LIVE_METRICS_UNAVAILABLE.

## Observed, sanitized from the local terminal

- OpenShift Local bundle: 4.22.7; CRC VM started, initially several operators progressed, then reported stable.
- Repository freshly cloned and script `bash scripts/collect-local-inventory-readonly.sh oc` launched from repository root under Git Bash on Windows.
- Collector markers: `I1_COLLECTION_START=2026-10-10T07:55:38Z`, `I1_COLLECTION_FINISHED=2026-10-10T07:55:51Z`, `READ_ONLY=true`.
- Local output directory: `evidence/local/private-20261010T075538Z/` (**local workstation only, not uploaded or independently checked here**).
- `pod-resources.csv`, `pvc-requests.csv`, `node-allocatable.csv` expected from successful script statements; contents **NOT PROVIDED** and cannot be independently validated.
- Both `oc top pods -A --containers` and `oc top nodes` were reported unavailable. Original stderr is in local `top-pods-warning.txt`, not provided.
- **No secret, kubeadmin credential, raw system namespace list or login material has been committed.** Never copy command output containing credentials into this public repository.

## Interpretation

This execution demonstrates that the collector ran and its read-only API queries exited successfully. It **does not** prove measured pod CPU/memory or close I1. After CRC startup, `metrics.k8s.io` aggregation/Prometheus Adapter may not be ready or may fail for authorization/health reasons; diagnose from the stderr and read-only APIService/operator status. Do **not** install an extra metrics-server or alter cluster monitoring without proving the root cause.

## Next non-mutating checks

Run from Git Bash in the same workspace:

```bash
oc whoami
oc get co monitoring
oc get apiservice v1beta1.metrics.k8s.io
oc adm top nodes
oc adm top pods -A
cat evidence/local/private-20261010T075538Z/top-pods-warning.txt
wc -l evidence/local/private-20261010T075538Z/*.csv
```

Never paste password or token output. Review errors before sharing for path/host data. `oc top` is only a current snapshot; P95/P99 requires multiple Prometheus samples over a meaningful historical window.

## Next I1 evidence gate

1. Obtain safe aggregated counts and requested CPU/memory from the CSV (without publishing raw node and pod names).
2. Recover resource metrics API or query the existing OpenShift monitoring stack.
3. Capture P95 usage, PVC used bytes, data retention and estimated IOPS as appropriate.
4. Revisit cloud node count and FinOps price model after evidence.

**I1 status: ACTIVE / LOCAL_COLLECTOR_EXECUTED / LIVE_USAGE_AND_FULL_BOM_PENDING.**

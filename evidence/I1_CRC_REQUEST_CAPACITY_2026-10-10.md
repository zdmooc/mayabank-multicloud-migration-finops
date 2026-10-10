# I1 — CRC request capacity and inventory evidence, 2026-10-10

**Scope:** sanitized numerical stdout provided by the operator from a local read-only collector run on 2026-10-10. This file contains no raw pod names, node names, secrets or token data. The underlying CSV files stay local in the gitignored `evidence/local/` folder and **have not been independently fetched**.

**Revisions observed**
- `git pull --ff-only`: fast-forward on `main` to then-current `a925d24` before run; this is **not** evidence of the current HEAD at the time of writing.
- Numerical aggregation from prior local capture `evidence/local/private-20261010T075538Z`.
- Re-collection using corrected metrics dispatcher from **2026-10-10 08:10:41Z to 08:10:47Z**, at `evidence/local/private-20261010T081041Z`.
- Re-collection printed `POD_TOP=AVAILABLE_CONTAINER_LEVEL_CURRENT_SAMPLE_ONLY` and `NODE_TOP=AVAILABLE_CURRENT_SAMPLE_ONLY`. The underlying **new** top and CSV values are not supplied here.

## Inventory from the first capture

| Indicator | Reported |
|---|---:|
| Nodes | 1 |
| Node allocatable CPU | 7.80 vCPU = 7,800m |
| Node allocatable RAM | 23.02 GiB = approximately 23,572 MiB |
| Pod records, all phases | 272 |
| Pod phases | Running 149, Pending 3, Succeeded 91, Failed 29 |
| Containers in Running or Pending pods | 220 |
| Containers with no explicit CPU request | 23 |
| Containers with no explicit memory request | 23 |
| PVC declared | 15 |
| PVC Bound | 15 |
| Total declared PVC storage requests | 52.00 GiB; **not used bytes** |

## Requests against node allocatable, numerical derivation

Values from the supplied summarizer, with percentages derived from the reported 7.80 CPU / 23.02 GiB allocatable. The node's memory capacity was rounded to two decimals by the collector, so memory percentages and margins are **approximate**.

| Scope | CPU requests | CPU / allocatable | RAM requests | RAM / allocatable |
|---|---:|---:|---:|---:|
| Running pods only | 7,318m | **93.82%** | 23,267 MiB | **98.70%** |
| Running + Pending pod containers | 7,348m | **94.21%** | 23,457 MiB | **99.51%** |
| Difference from Pending pod containers | 30m | n/a | 190 MiB | n/a |
| Allocatable less Running+Pending requests | **452m** | **5.79%** | **~115 MiB** | **~0.49%** |

**Important limitations**

- The Running+Pending aggregate includes Pending pods that may not have been scheduled. It is *not* by itself the exact scheduler-committed requests on a node. Even Running-only requests are already near the allocatable memory bound.
- The summarizer excludes `initContainers` and Kubernetes PodOverhead; scheduler effective requests can differ from plain `sum(containers[].requests)`. This preliminary measurement requires reconciliation with `oc describe node` or scheduling API allocations before making an exact bin-packing claim.
- Missing requests (23 container records) are **not** equal to 23 completely uncontrolled pods; they require targeted resource-owner review and may be sidecars.
- The 120 Succeeded/Failed pods are historical/non-running items in the inventory and must not be mistaken for current cost-driving workers.
- All 15 PVCs being Bound says nothing about actual used bytes, IOPS, backup retention or readiness for Cloud.
- The first live node sample, taken separately via `oc adm top nodes`, was **1,765m (22%) CPU and 18,367 MiB (77%) RAM**. Actual utilization and reserved requests are different metrics taken at different instants.
- The ~23 GiB node allocatable capacity reported here clarifies the discrepancy with the **older** ~32 GiB CRC baseline, but this file alone does not establish why the configured or allocatable size differs (VM config and kubelet reservations require a separate check).
- Data Lakehouse Kind is a separate target and **not included in CRC aggregation**. The 3 pending pods were not explained by status events and must not be labeled unschedulable solely based on headroom.

## Multi-cloud interpretation

- The first 2×(4 vCPU, 16 GiB) cloud-worker demo profile remains a **selected workload** scenario; it has not been proved able to host the entire CRC application/observability/control workload inventory at once.
- A 2-node configuration's 8 vCPU / 32 GiB are **nominal totals**, not allocatable after Kubernetes system services and safety margin; with ~7.3 vCPU already requested in CRC, 2×4 vCPU has a narrow theoretical CPU margin even before provider-specific reserves.
- The CRC `openshift-*` monitoring, etcd, control-plane and Operators must **not** be charged as a 1:1 replacement workload on managed AKS/EKS/GKE; those providers differ in control-plane ownership, infrastructure reservations and managed monitoring fees.
- No grounds yet to increase the 8/24/40 vCPU planning scenarios to official requirements or to infer HA from observed one-node requests.
- Before choosing SKU/node counts, obtain namespace category aggregates, exact workload profile, node/pod scheduling, P95/P99 actual use, memory limit/OOM and PVC used-byte/I/O evidence.

## Next read-only checks

```bash
cd /c/workspaces/mayabank-multicloud-migration-finops
git pull --ff-only

python scripts/summarize-local-inventory.py \
  evidence/local/private-20261010T081041Z

# Optional: check summaries for first capture for before-after consistency.
python scripts/summarize-local-inventory.py \
  evidence/local/private-20261010T075538Z
```

These commands emit only numeric aggregates; do not upload the raw CSV or `top-pods-now.txt` to this public repository. Review any terminal transcript for sensitive host information.

**Gate:** `I1_CRC_REQUESTS_OBSERVED / I1_OPEN`; sufficient to establish **request-pressure risk** but not cloud-ready sizing, P95 or full TCO.

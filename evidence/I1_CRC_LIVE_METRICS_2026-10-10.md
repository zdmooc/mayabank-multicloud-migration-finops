# I1 — CRC OpenShift metrics live: root cause and safe aggregate

**Observation:** user terminal output on 2026-10-10 following a completed collector run at 07:55 UTC. **Status:** LIVE_INSTANTANEOUS_METRICS_OBSERVED / HISTORICAL_TREND_NOT_PROVEN / I1_OPEN.

## Root cause of first collection warning

- `oc get co monitoring`: OpenShift monitoring 4.22.7 `AVAILABLE=True, PROGRESSING=False, DEGRADED=False`.
- `oc get apiservice v1beta1.metrics.k8s.io`: OpenShift monitoring metrics-server `AVAILABLE=True`.
- `oc adm top nodes` and `oc adm top pods -A` both **SUCCEEDED**.
- The repository's former script incorrectly invoked `oc top`, which fails with `unknown command "top" for "oc"`; that was a **collector CLI dispatch defect**, not a metrics outage.
- Fixed: `oc adm top ...` for OpenShift, `kubectl top ...` for standard Kubernetes; pod-level fallback if the installed client rejects `--containers`.

## One-time measured node snapshot

| Node aggregate | Observed |
|---|---:|
| CPU | **1,765m (22%)** |
| Memory | **18,367 Mi (77%)** |

**Do not infer total node memory from the older October 3 ~32GiB snapshot**. The observed 18,367Mi / 77% implies a capacity/percentage denominator near 23.3GiB; confirm from the new local `node-allocatable.csv` or `crc config view`. CPU/Memory node readings are one sample only, not 7-day P95.

## Sanitized per-pod metric aggregation

Aggregated **only from the supplied `oc adm top pods -A` text**, without preserving pod IDs or machine credentials:

| Group by namespace prefix | Visible pod rows | Sum CPU from pod rows | Sum memory from pod rows |
|---|---:|---:|---:|
| `openshift-*` (operators, monitoring, control-plane, GitOps, etc.) | 108 | 880m | 13,753 Mi |
| Other namespaces (synthetic applications and supporting hostpath provider) | 39 | 242m | 5,003 Mi |
| **Visible pod samples** | **147** | **1,122m** | **18,756 Mi** |

Selected other namespace aggregates:
- Instant Payments: 18 pods, 171m CPU, 3,022 Mi memory.
- Keycloak specialist: 3 pods, 16m CPU, 727 Mi memory.
- Maya Freelance: 3 pods, 9m CPU, 375 Mi memory.
- TradeOps: 4 pods, 13m CPU, 289 Mi memory (does **not** indicate the full agent stack is active).
- IBM MQ local: 5 pods, 21m CPU, 283 Mi memory.
- API Management: 2 pods, 3m CPU, 142 Mi memory.
- Decision API: 1 pod, 1m CPU, 14 Mi memory.
- Shared OTel collector: 1 pod, 3m CPU, 78 Mi memory.
- Platform Operator: 1 pod, 1m CPU, 20 Mi memory.

**Warning on comparability:** adding `oc adm top pods` samples does not have to equal a simultaneous `oc adm top nodes` sample. Samples are taken at potentially different instants and container vs node accounting differs; node total CPU includes host processes. Pod memory sum here (18,756Mi) is slightly above reported node memory (18,367Mi). Do not use the difference as a reliable infrastructure reserve or an arithmetic bug.

## Cloud sizing implications

- Heavy OpenShift local control-plane/monitoring overhead is **not** transplanted unchanged to customer worker nodes on managed AKS/EKS/GKE; each provider still has its own system pods, node-allocatable reservations and paid monitoring costs.
- Main app footprint is much lower than node total, especially with TradeOps parked/limited. A generic 24-vCPU cloud pool is **not demonstrated as necessary**; benchmark each **explicit concurrent deployment profile**.
- Node RAM utilization is significant in this CRC snapshot (77%); avoid assuming unlimited memory headroom.
- Single-node node `top` values, not P95 or HA evidence, cannot qualify a region's production instance size.
- Data Lakehouse Kind footprint is a **separate cluster** and not in this `oc adm top` output.

## Next safe check

Run from Git Bash after `git pull --ff-only`:

```bash
python scripts/summarize-local-inventory.py evidence/local/private-20261010T075538Z
# Optional fresh read-only collection after fix
bash scripts/collect-local-inventory-readonly.sh oc
```

Share only the numeric summarizer output. Do not publish `oc login` output, credentials, original `oc adm top pods` list, private hostnames, source kubeconfig or raw node/PVC CSVs in the public repository.

**I1 remains open**: rendered effective requests and limits, measurement trends/P95, used disk and IOPS, network, workload concurrent profile and official complete Cloud BOM not supplied.

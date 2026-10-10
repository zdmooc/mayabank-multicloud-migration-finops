# I1 — CRC requests versus observed container metrics by workload group

**UTC source window:** local collector 2026-10-10 08:10:41–08:10:47. **Date registered:** 2026-10-10. **Evidence:** operator-provided numeric output from `python scripts/summarize-local-inventory.py --workload-groups --observed-top evidence/local/private-20261010T081041Z`. Private CSV and raw `oc adm top` data remain on the user's local PC. No live cluster access or raw identity matching has occurred in this GitHub session.

**Gate:** `I1_CRC_GROUPED_REQUESTS_AND_SINGLE_POINT_USAGE_OBSERVED / I1_OPEN`, NOT P95, NOT load tested, NOT cloud sizing validated.

## 1. Snapshot and inventory

- OpenShift CRC: **1 node, 7.80 vCPU allocatable, 23.02 GiB memory allocatable**.
- 270 pod objects: **149 Running, 0 Pending, 92 Succeeded, 29 Failed**.
- 217 regular containers in the Running phase according to the resource CSV; 23 entries do not specify CPU requests, and 23 do not specify RAM requests.
- Requests across these active containers: **7,318m CPU and 23,267 MiB memory**, around **93.82%** and **98.68%** of node allocatable respectively.
- `oc adm top pods -A --containers` produced **216 metric rows**, fewer than the **217 active regular-container records**; exact per-container coverage and scrape timing have **not** been verified.
- The observed aggregate from parsed metric rows is **1,194m CPU / 19,064 MiB memory**. Group totals reconcile to this exact sum; it is not identical to `oc adm top nodes` and should not be used as total node consumption.
- PVC: **15 of 15 Bound, 52 GiB requested**, not bytes used.

## 2. Comparison — group request totals vs one-time usage

| Group / namespace classification | CPU request | CPU top | CPU top/request | RAM request (MiB) | RAM top (MiB) | RAM top/request |
|---|---:|---:|---:|---:|---:|---:|
| OpenShift namespace prefix (108 pods; 173 metric rows) | 4603m | 974m | 21.2% | 14305 | 13965 | **97.6%** |
| Payments including Kafka/Postgres/monitoring (19 pods; 19 metric rows) | 505m | 128m | 25.3% | 3200 | 3079 | **96.2%** |
| TradeOps partial active 4 pods | 225m | 18m | 8.0% | 768 | 295 | 38.4% |
| Maya Freelance 3 pods | 250m | 11m | 4.4% | 736 | 410 | 55.7% |
| Decision 1 pod | 100m | 1m | 1.0% | 128 | 12 | 9.4% |
| IBM MQ namespace 5 pods | 850m | 27m | 3.2% | 1792 | 278 | 15.5% |
| Keycloak + operator + DB 3 pods | 600m | 21m | 3.5% | 1730 | 746 | 43.1% |
| API namespace 2 pods (gateway/product mix) | 35m | 3m | 8.6% | 288 | 154 | 53.5% |
| Shared OTel 1 pod | 50m | 3m | 6.0% | 128 | 51 | 39.8% |
| Shared Platform Operator 1 pod | 50m | 1m | 2.0% | 64 | 19 | 29.7% |
| Hostpath provisioner 1 pod; 4 metric rows | 0m | 7m | n/a | 0 | 55 | n/a |
| Unclassified other 1 pod; no metric rows | 50m | no sample | n/a | 128 | no sample | n/a |
| **Total group sums** | **7318m** | **1194m** | **16.3% (non-identical set)** | **23267** | **19064** | **81.9% (non-identical set)** |

**Important:** a quotient `observed usage / resource request` is **NOT Kubernetes CPU or memory percent utilization against physical capacity**. Requests are scheduler reservations, not hard RAM ceilings; actual usage can exceed a request. The table is descriptive and its denominator is incomplete if metrics are missing. The `top` command reports rounded, momentary values.

## 3. Critical findings for cloud sizing

1. **Memory pressure is the leading request and workload-protection issue.** The OpenShift-prefix group uses approximately 97.6% of requested RAM and the Payments namespace approximately 96.2% at that point in time. Do not lower their memory requests without a peak/OOM/working-set review.
2. **CPU is low compared with requests at that instant**: 1194m measured across top rows versus 7318m requested across recorded containers (16.3% arithmetic quotient). Do not use this snapshot alone to select cheaper, smaller instances: spikes, busy intervals, rollout, replication, time-in-zone and P95 are unknown.
3. **Payments is stateful plus support components, not only 5 business APIs**: its 505m/3200Mi namespace requests and 128m/3079Mi observed usage cannot be used as a pure application tier target. Cloud-managed DB/Kafka/identity/network migration decisions may change both worker demand and monthly service charges.
4. **OpenShift group is not entirely removable on managed K8s.** Provider-owned API server/etcd is different from worker-hosted GitOps, Pipelines, networking, observability, security and operators. Which to replace or retain is a per-component architecture decision.
5. **TradeOps 4 pods are incomplete** compared to the full AI/RAG/GPU inference architecture; local Qwen/Ollama GPU sizing is separately tracked, and Kind Data Lakehouse is **not in this CRC snapshot**.
6. The current **two-worker x 4-vCPU/16-GiB targeted demo** is still a selective pilot hypothesis. There is no evidence to select 6 versus 10 workers or to approve a provider from this data.
7. Wero's historical `wero-poc` (scale-zero/reference) is a **separate recovery/archive study** from the Instant Payments `instant-payments-local` runtime. Do not awaken it or add idle Deployment objects to active resource sums.

## 4. Residual evidence checks, ordered

- **I1-A:** ensure container-level metric matching of `top-pods-now.txt` with `pod-resources.csv` (the raw records never leave the local ignored folder), record aggregate unmatched counts without emitting identities.
- **I1-B:** select the concrete Instant Payments pilot slice and break apart business APIs, databases, Kafka, monitoring and shared IAM/API and cluster-system components.
- **I1-C:** collect properly filtered 7–30 day CPU/RAM P95/P99 and OOM/restart signals under a documented workload, not only after local CRC startup.
- **I1-D:** verify used PVC bytes, IOPS, backups, data consistency and network/egress.
- **I1-E:** make an official region/service/SKU-level bill of materials for AKS/EKS/GKE (incl. control plane, node allocatable, identity, ingress/LB/NAT, storage, managed databases, logging, AI/MQ license).
- **I1-F:** inspect Kind Lakehouse independently; decide explicit workload concurrency.

**Decision:** `I1_ACTIVE`; no cloud deployment, paid budget, 8/24/40-vCPU proposal promotion or Wero removal is authorized by this comparison.

## Separate PostgreSQL workload inventory — 2026-10-10

A later *read-only* OpenShift Deployment/StatefulSet scan identified **9 PostgreSQL server workloads (8 Ready/1 replica, 1 legacy Wero at 0 replicas)**, spanning 7 namespaces. Breakdown: 3 Instant Payments, 1 Maya Freelance, 1 IBM MQ payments, 1 Keycloak, 1 Tekton Results, 1 TradeOps, 1 Wero historical. Seven image tags use floating `latest`, one uses `postgres:16` and one uses a PostgreSQL 15 digest.

This identifies **workloads**, not number of logical databases or proven DB client connections. The eight ready PostgreSQL workloads are not eight VMs. PostgreSQL resource requests, actual sampled CPU/RAM, used PVC bytes and managed database migration costs must be separately modeled; do not use an aggregated Payments namespace as application-only sizing.

Canonical owner inventory: https://github.com/zdmooc/cadrage_202682030/blob/main/portfolio/CRC_POSTGRESQL_INVENTORY_2026-10-10.md

No CRC changes or PostgreSQL scaling/removal authorized; Wero historical remains scale-zero.

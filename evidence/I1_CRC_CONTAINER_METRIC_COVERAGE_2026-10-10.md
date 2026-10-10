# I1 — CRC container-level request/metric coverage, 2026-10-10

**Scope:** sanitized stdout supplied by the CRC operator, generated locally from `evidence/local/private-20261010T081041Z` using `scripts/check-local-top-coverage.py`. Original pod identities, raw pod CSV, node data and top metric table remain on the workstation. **Evidence class:** LOCAL_OPERATOR_REPORTED_IDENTITIES_RECONCILED; no independent remote cluster access.

## Matching result

| Control | Value |
|---|---:|
| Regular containers in Running pods in request CSV | **217** |
| Per-container lines in `oc adm top pods -A --containers` | **216** |
| Exact triples matched (namespace, pod, container) | **216** |
| Running containers missing from top sample | **1** |
| Top rows without a Running container in the request CSV | **0** |
| Identity coverage of the Running request inventory | **216/217 = 99.54%** |
| Coverage of observed top metric rows | **216/216 = 100%** |

Only `unclassified_other` contains an unmatched declared Running container. Its declared request is **50m CPU and 128 Mi RAM**. No top CPU/RAM sample exists for it. **Do not assume zero consumption or classify its cause from the anonymized output alone.** This can be a timing/metrics readiness difference or another condition requiring local inspection.

## Corrected matched-set comparison

The *same 216 matched container identities*, after excluding that missing top record, have **7,268m requested CPU / 23,139 Mi requested RAM**, with **1,194m observed CPU / 19,064 Mi observed RAM**. These ratios are **16.43%** observed/request CPU and **82.39%** observed/request RAM (single snapshot), not node CPU utilization or P95.

The previously reported 1,194m/7,318m (16.32%) and 19,064Mi/23,267Mi (81.94%) ratios were arithmetic comparisons between slightly different container populations. Preserve them as historical descriptive aggregate ratios, but prefer **matched-set** ratios in further analysis.

| Group | Matched rows | CPU requested/observed | RAM requested/observed |
|---|---:|---|---|
| OpenShift namespace prefix | 173 | 4603m / 974m | 14305 Mi / 13965 Mi |
| Payments | 19 | 505m / 128m | 3200 Mi / 3079 Mi |
| TradeOps (partial) | 4 | 225m / 18m | 768 Mi / 295 Mi |
| IBM MQ | 5 | 850m / 27m | 1792 Mi / 278 Mi |
| Keycloak/identity | 3 | 600m / 21m | 1730 Mi / 746 Mi |
| API mixed | 2 | 35m / 3m | 288 Mi / 154 Mi |
| Maya Freelance | 3 | 250m / 11m | 736 Mi / 410 Mi |
| Decision API | 1 | 100m / 1m | 128 Mi / 12 Mi |
| Shared OTel | 1 | 50m / 3m | 128 Mi / 51 Mi |
| Shared Platform Operator | 1 | 50m / 1m | 64 Mi / 19 Mi |
| Local hostpath provisioner (4 containers) | 4 | 0m / 7m | 0 Mi / 55 Mi |
| Unclassified other | 0 | no measured pair | no measured pair |
| **Matched total** | **216** | **7268m / 1194m** | **23139 Mi / 19064 Mi** |

## Operational implications

- Historical CRC node utilization and the sum of per-container metrics need not agree: node metrics include host work, time windows differ, and Kubernetes request accounting is not measured consumption.
- Requests can be zero while running usage is nonzero (local hostpath provisioner); do **not** use utilization/request ratios as hard capacity ceilings.
- Payments memory utilization near the request at one instant (3079/3200 Mi = 96.22%) requires load/P95 and OOM history before adjusting requests.
- OpenShift-prefix memory top/request 13965/14305 Mi = 97.62%, but **not all** those containers map directly to managed-cloud workers.
- 216/217 matching means the collector's identity mapping is highly complete at that single moment, but it does not prove 7-day capacity, peak demand or app behavior.
- The historical Wero `wero-poc` reference is a separate audit; **do not** reactivate or delete it as part of MultiCloud I1.
- Kind Data Lakehouse metrics and full AKS/EKS/GKE BOM remain missing.

## I1 next gates (ordered)

1. Confirm the one unmeasured container locally with a read-only identity check and optional new capture; never publish names or credentials in the public repository.
2. Record **P95/P99 CPU and RAM for peak/business windows**, plus restarts/OOM and actual persistent-storage consumption, using existing monitoring; avoid concluding from single snapshot.
3. Extract an **explicit Instant Payments pilot deployment slice** (business API + selected identity, DB, broker, ingress, monitoring), with clear managed-service alternatives and resource allocations.
4. Measure Kind Data Lakehouse separately, then obtain provider-official region/SKU full bill of materials including LB/NAT/egress, stateful storage, backup, licenses and AI.
5. Maintain `ASSESSMENT_ONLY / I1_OPEN`; no paid Cloud resources until human-approved scope/budget/teardown.

**Milestone:** `I1_CRC_CONTAINER_METRIC_COVERAGE_99_54PCT / I1_OPEN`.

# I1 — CRC grouped workloads and migration sizing gates — 2026-10-10

**Status:** I1_CRC_WORKLOAD_GROUPS_OBSERVED / I1_OPEN. **Input:** sanitized output of local script `scripts/summarize-local-inventory.py --workload-groups evidence/local/private-20261010T081041Z`, after operator fast-forwarded `main` from `773a9b2` to `18bfbe4`. Observation is a **single snapshot** of declared Kubernetes regular-container resource requests from 2026-10-10 08:10 UTC, not runtime CPU/memory utilization, trend P95, a full application inventory or a Cloud bill of materials. No original local CSVs were uploaded or inspected.

## 1. Results verified by arithmetic over the user's output

| Synthetic grouping from exact namespace labels | Running pods | CPU requests (m) | RAM requests (Mi) |
|---|---:|---:|---:|
| OpenShift namespace prefix (all) | 108 | 4,603 | 14,305 |
| Payments namespace incl. databases, Kafka, observability & UI | 19 | 505 | 3,200 |
| TradeOps namespace (only active four pods, incomplete platform) | 4 | 225 | 768 |
| Maya Freelance namespace incl. database | 3 | 250 | 736 |
| Decision API namespace | 1 | 100 | 128 |
| IBM MQ namespace incl. specialized stateful dependencies | 5 | 850 | 1,792 |
| Shared Keycloak namespace incl. database/operator | 3 | 600 | 1,730 |
| API namespace, mixed gateway + product | 2 | 35 | 288 |
| Shared OpenTelemetry namespace | 1 | 50 | 128 |
| Shared Platform Operator namespace | 1 | 50 | 64 |
| Local hostpath provisioner namespace | 1 | 0 | 0 |
| Unclassified other namespace (no attribution) | 1 | 50 | 128 |
| **All** | **149** | **7,318** | **23,267** |

All group sums reconcile with the earlier `node_allocatable` snapshot:
- The four **product-labelled namespace groups** Payments, TradeOps, Freelance and Decision have 27 pods / **1,080m CPU / 4,832 Mi RAM (4.719 GiB)**. These group names do **not** mean stateless-only; notably Payments and Freelance embed stateful applications, databases and observability.
- The other non-`openshift-*` groups have 14 pods / **1,635m CPU / 4,130 Mi RAM (4.033 GiB)**, including MQ, identity, API, shared OTel and operator.
- Combined non-`openshift-*`: 41 pods / **2,715m / 8,962 Mi (8.752 GiB)**.
- Prefix `openshift-*`: 108 pods / **4,603m / 14,305 Mi (13.970 GiB)**.
- Node allocatable reported: **7,800m / 23.02 GiB**; requests total **7,318m / 23,267 Mi**, with ~482m CPU / 310.35 Mi memory headroom. Relative CPU **93.82%**, RAM **98.68%**. These are **requests**, not observed usage or 7-day P95.
- 0 Pending pods in this 08:10 snapshot; the earlier three Pending were a separate timepoint. There are 92 Succeeded and 29 Failed historical pod records, excluded from active sums.
- 23 active container records have no explicit CPU request and 23 no explicit memory request. Not proof that all 23 pods lack enforcement; admission, LimitRange and multiple-container pods need review.
- All 15 PVC Bound, **52 GiB requested, used bytes unknown**.

## 2. Architecture interpretation — do not misuse namespace labels

1. **The Kubernetes namespace is not a migration unit by itself.** A Payments namespace can contain five stateless business services, Kafka, three PostgreSQL databases, MongoDB, OTel/Alloy and dashboards. Moving these as one managed-Kubernetes pod set may be the wrong economic/availability decision.
2. **The `openshift-*` prefix is not pure disposable control plane.** It can include deployed GitOps, Pipelines/Tekton, monitoring and Operators. Managed AKS/EKS/GKE supply a provider-run control plane but still need selected worker-hosted agents, CNI, ingress, log collection and application capability controllers. Analyze the service owner and target separately.
3. **MQ and Keycloak remain live support workloads.** Their requests (together **1,450m / 3,522 Mi**) already represent a substantial part of the non-prefix pool, but some may be excluded from a narrowly scoped first Instant Payments pilot if their contracts are replaced or externalized with evidence.
4. **TradeOps 4 active pods != entire TradeOps Helm profile.** Local Qwen/Ollama and dormant AI services are not included in this CPU/RAM snapshot. GPU or model API expense needs an independent bill-of-material lane.
5. **Data Lakehouse Kind remains wholly separate** from CRC and must have its own target/runtime capacity and storage sizing.
6. **No Cloud production or HA readiness claim.** Worker placement, replicas, AZ, system reservations, access/security, data consistency, rollback, operating cost and peak workload tests are still unproven.

## 3. Explicit pilot variants — not priced or approved

| Boundary | Included workload concepts | Excluded / separate decisions | Stage |
|---|---|---|---|
| P0 — Payment business-slice | Chosen Payments APIs and synthetic E2E; minimum auth and eventing integration contract | Local Kafka/Postgres may be managed/external; cloud-side ingress/system resources not in the numeric group | **SELECT_BOUNDARY / NOT_SIZED** |
| P1 — Payments namespace as-is | 19 CRC-running pods, **505m / 3,200 Mi requests** at this snapshot | Add Keycloak, API gateway, OTel, GitOps / cluster system pool as required; cloud DB/event and operator choice | **REFERENCE_ONLY / NOT_PORTABILITY_PROVEN** |
| P2 — All non-OpenShift namespaces | 41 CRC-running pods, **2,715m / 8,962 Mi requests** | Reinstatement of needed `openshift-*` components, full TradeOps, Kind lakehouse, HA overhead and Cloud data services | **REFERENCE_ONLY / NOT_DEPLOYABLE_PROFILE** |

The earlier `targeted-demo` planning scenario (2 workers × 4 vCPU / 16 GiB) is **nominal worker capacity** for a *selected slice*, never a verified complete migration of P1 or P2. It is premature to amend the economic model, choose a `winner` provider, or close I1 from these requests alone.

## 4. Next reproducible non-mutating measurements

- Evaluate actual **single-timepoint** per-container `oc adm top pods -A --containers` resource usage by the **same workload groups** using a local read-only, privacy-preserving aggregation. Report request-vs-observed ratios **as exploratory, not P95**.
- Review the 23 containers without explicit requests and reasons for prior Pending; check OOM/restarts and running Pod phase, without publishing raw names.
- Identify exact Payments business E2E slice vs support service dependencies, especially data/state, before determining target node allocatable needs.
- Use Prometheus P95/P99 over multi-day peak/load windows, plus storage used bytes/IOPS, Kafka lag, throughput, network and Kind evidence.
- Get official provider regional SKU pricing and the complete bill of materials. No paid provisioning before human approval.

**Evidence level:** `LOCAL_CRC_DECLARED_REQUESTS_SNAPSHOT`. **I1 status:** `PARTIAL / OPEN`.

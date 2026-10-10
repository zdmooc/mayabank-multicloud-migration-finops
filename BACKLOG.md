# MultiCloud Migration & FinOps — backlog

**Date:** 2026-10-09 | **Status:** ASSESSMENT_ONLY | **Cloud deployment:** NOT AUTHORIZED

| Gate | Outcome and acceptance | Status |
|---|---|---|
| I0 | Dated inventory, owner map, initial sizing and cost hypotheses | DOCUMENTED_BASELINE; measurement gaps remain |
| I1 | Regional service/SKU pricing, rendered requests/limits, measured usage, dependency graph, target HLD | **CRC_GROUPED_SINGLE_SNAPSHOT_OBSERVED / P95_AND_FULL_BOM_OPEN** |
| I2 | Terraform/Kustomize/Helm non-mutating render and review, least privilege, budgets, teardown runbook | OPEN |
| I3 | Bounded Instant Payments AKS pilot, authenticated E2E, metering, rollback, destroy | BLOCKED: prior explicit approval |
| I4 | Equivalent EKS and GKE pilots, comparable evidence and cleanup | BLOCKED: I3 + approval |
| I5 | Selective TradeOps, Decision AI, Lakehouse, MQ and other app waves | PLANNED_ONLY |
| I6 | Multi-AZ/stateful resilience, backups, recovery, performance, RPO/RTO and FinOps validation | PLANNED_ONLY |

## I1 progress — 2026-10-09

- [x] Re-read the canonical MayaBank repo classification and local runtime matrix.
- [x] Extract selected CPU/RAM requests from GitHub workload manifests; record **19 source rows / partial** rather than all workload estimates.
- [x] Obtain published official AKS/EKS/GKE standard cluster-management fees, and secondary comparator Paris-region instance rates.
- [x] Produce **compute + cluster only** estimates with explicit omitted charges, public sources and verification date.
- [x] Add sanitized **read-only** local CRC/Kind collection script and PromQL recipes.
- [x] Add offline CI contract validation for manifests and FinOps subtotals.
- [ ] Render active application overlays and deduplicate system/pod/stateful requests against real running namespaces.
- [ ] Capture actual CRC/Kind per-container usage and P95, volume used bytes, network/throughput, load.
- [ ] Collect official VM SKU prices, managed storage/database/network/network-egress/SLA/licensing BOM.
- [ ] Final HLD, network/security and cutover risk acceptance; I1 **remains open**.

## I1 CRC live snapshot — 2026-10-10

- [x] CRC monitoring operator and metrics APIService confirmed available; `oc adm top nodes/pods` returned one live sample.
- [x] Corrected collector: `oc adm top` for OpenShift versus `kubectl top` for Kubernetes; added CI mock regression and fallback.
- [x] Recorded safe rollup: node 1765m CPU (22%), 18367Mi RAM (77%); 147 visible pod rows (108 `openshift-*`, 39 elsewhere).
- [ ] Analyze the user's local CSV request/limit and node allocatable files with the safe offline summarizer. Files are not in GitHub.
- [ ] Capture 7–30-day P95, actual PVC usage/IOPS/network and full provider-specific service BOM before closing I1.

See [live sanitized measurements](evidence/I1_CRC_LIVE_METRICS_2026-10-10.md). Local CRC OpenShift overhead is not transferred 1:1 to the managed-cloud worker pool.

## I1 update — 2026-10-10 08:10 UTC, local request saturation measured

- [x] Read-only `oc` collection **fixed and confirmed**: `POD_TOP=AVAILABLE_CONTAINER_LEVEL_CURRENT_SAMPLE_ONLY`, `NODE_TOP=AVAILABLE_CURRENT_SAMPLE_ONLY`.
- [x] Analyzed sanitized numerical inventory: 1 node, 7.80 allocatable vCPU, 23.02 GiB allocatable RAM; 149 Running pods, 3 Pending pods, 91 Succeeded, 29 Failed.
- [x] Running container requests: 7318m CPU (**93.82% allocatable**) / 23267 Mi RAM (**98.70% allocatable**).
- [x] Running+Pending regular-container requests: 7348m CPU (**94.21%**) / 23457 Mi RAM (**99.51%**). Pending is not necessarily scheduled; these percentages are **not** an exact node scheduler accounting.
- [x] 15/15 PVC bound, 52 GiB capacity requested (**not actual bytes used**); 23 running/pending containers each lacking explicit CPU and RAM request.
- [x] Added safe prefix-aggregate local summarizer and synthetic CI tests.
- [ ] Analyze new local prefix-category summary; reconcile running vs scheduled requests including initContainers / pod overhead, and verify 3 Pending reasons.
- [ ] Collect P95, storage used bytes/IOPS, exact active workload overlay and official complete BOM before **I1_CLOSED**.

[Detailed I1 capacity observation](evidence/I1_CRC_REQUEST_CAPACITY_2026-10-10.md). 2×4-vCPU demo workers remain a selective-workload hypothesis, **not** proven adequate for all simultaneous CRC services. Kind Data Lakehouse remains separate.

## I1 namespace segmentation — 2026-10-10

- [x] Updated CRC inventory: 149 Running pods; zero Pending; 92 Succeeded and 29 Failed.
- [x] OpenShift-prefix namespaces: 108 Running pods, 4603m CPU requests and 14305 Mi memory requests.
- [x] Other namespaces: 41 Running pods, 2715m CPU requests and 8962 Mi memory requests.
- [x] All Running containers: 7318m CPU / 23267 Mi RAM requested; node allocatable 7800m CPU / about 23.02 GiB RAM.
- [x] PVC requested: 52 GiB across 15 Bound claims. Used bytes not measured.
- [x] Optional read-only grouped workload analysis added to local summarizer.
- [ ] Finish cloud target workload classification, P95 usage, actual disk and IOPS, node headroom, and complete regional cost BOM.

See evidence/I1_CRC_NAMESPACE_SEGMENTATION_2026-10-10.md. Status: I1 OPEN.

## I1 grouped products and shared dependencies — 2026-10-10

- [x] Local `--workload-groups` evidence reconciles to **149 Running pods / 7318m CPU / 23267 MiB RAM**.
- [x] Product-labelled namespace groups: **27 Running pods / 1080m CPU / 4832 MiB**. Includes databases and support services inside product namespaces; **not pure stateless application load**.
- [x] Other non-OpenShift groups: **14 pods / 1635m CPU / 4130 MiB**. Includes Keycloak, IBM MQ, shared OTel, platform operator and mixed API workloads.
- [x] OpenShift-prefix platform groups: **108 pods / 4603m CPU / 14305 MiB**. Not all dispensable on managed Kubernetes.
- [x] [Scoped migration comparison](evidence/I1_CRC_WORKLOAD_GROUPS_2026-10-10.md): Payments 19 pods / 505m / 3200Mi; TradeOps 4 / 225m / 768Mi (not full product); MQ 5 / 850m / 1792Mi; identity 3 / 600m / 1730Mi.
- [x] Added optional local `--observed-top` to compare these same namespace categories to a **single CPU/RAM usage snapshot**, not a P95.
- [ ] Run the new local snapshot comparison, select the exact Payments pilot slice, and separate business vs stateful/observability/identity components. Then collect P95, Kind inventory and provider full BOM. **I1 not CLOSED**.

## I1 CRC observed metrics versus scheduler requests — 2026-10-10

- [x] Snapshot by namespace group from `--observed-top` delivered by operator: **216 top container rows** vs **217 Running regular-container declarations**; exact identity coverage not established from summary only.
- [x] Top metric sums **1194m CPU / 19064 Mi memory** vs declared requests **7318m / 23267 Mi**, descriptive top/request ratios **16.3% CPU / 81.9% memory** (not validated same complete set or P95).
- [x] Payments **505m requests / 128m observed CPU** and **3200 Mi requested / 3079 Mi observed memory**; namespace includes Kafka/PostgreSQL and monitoring, not only APIs.
- [x] OpenShift-prefix **4603m/974m CPU** and **14305 Mi/13965 Mi RAM**, memory observed/request **97.6%**; cannot assume OpenShift overhead transfers 1:1 to managed Kubernetes.
- [x] Added [grouped usage evidence](evidence/I1_CRC_REQUESTS_VS_OBSERVED_2026-10-10.md) and offline [per-container identity coverage checker](scripts/check-local-top-coverage.py) with synthetic tests; no local raw CSV published.
- [ ] Operator executes the checker on the 08:10 capture and sends only aggregated results, establishing matched/missing top samples.
- [ ] Collect historical workload-aware P95/P99, OOM/restart signals, data IO/used volumes, Kind Lakehouse baseline and full provider regional BOM. **I1 stays OPEN.**

## I1 entry criteria

- [ ] Read current `cadrage_202682030` classification, roadmap and runtime deployment matrix.
- [ ] Read-only inventory from CRC + Kind: actual active vs parked pods; render overlays and report requests, limits and P95/P99 CPU/RAM.
- [ ] Size PVC used bytes, retention, replication, IOPS, network/egress and backup requirements.
- [ ] Obtain region/date/SKU-specific Azure, AWS and GCP quotes for VM, disks, LB, control plane, NAT, databases, observability and data transfer.
- [ ] Separate demo 160h, always-on 730h and dedicated stateful operation costs.
- [ ] Review OpenShift-specific APIs before choosing AKS/EKS/GKE.

## Separate workstream — TradeOps AI inference, local workstation vs GPU cloud (2026-10-09)

This evaluation is **not** evidence of I3/I4 AKS/EKS/GKE migration and does not authorize cloud spend.

- [x] Consolidate the complete 2026-10-09 discussion in [GPU local/cloud TCO](finops/AI_INFERENCE_TCO_LOCAL_STATIONS_AZURE_AWS_GCP_2026-10-09.md) (laptop alternative, local RTX/GB10 stations, Azure/AWS/GCP GPU SKUs, 4h/8h/24x7 hours, storage/energy, break-even limitations and public GitHub examples).
- [x] Record the [hybrid CRC -> private GPU inference HLD](architecture/TRADEOPS_HYBRID_GPU_INFERENCE_HLD_2026-10-09.md) (D-090 governance preserved).
- [ ] Verify official vendor GPU hourly prices, selected regions/zones/quotas and all-in monthly bill; obtain fresh local station quotations. Historical prices in the dossier are NOT verified offers.
- [ ] Decide whether usage is 4h x 22 weekdays or 4h x 30 calendar days; define model/concurrency, tokens/s, data and SLO before choosing hardware.
- [ ] Qualify an IaC **implementation owner** per ADR-001; prepare Terraform plan (VM, PD, VPC, IAM, Instance Schedule, budget), idempotent Ollama/vLLM bootstrap, protected endpoint and teardown, all **non-mutating** at first.
- [ ] After explicit spend approval only: quota and billing controls, deploy an isolated GCP L4 4h/day pilot, verify start/stop, cost, p95/model performance, and requalify D-090 external-provider security/evidence.
- [ ] Compare measured GPU rental OPEX against measured local power plus amortized station CAPEX; record decision in the master dossier.

## Human approval gate before any paid action

Account/region authorization + cap and alarms + IAM scope + reviewed plan + security/privacy + teardown receipt + explicit go/no-go. No autonomous apply/destroy, no provider tokens in this public repository.

**A published manifest is not deployment evidence; CRC single-node != HA; Kind 3 nodes != production.**

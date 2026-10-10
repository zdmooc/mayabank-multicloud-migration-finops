# MultiCloud Migration & FinOps — backlog

**Date:** 2026-10-09 | **Status:** ASSESSMENT_ONLY | **Cloud deployment:** NOT AUTHORIZED

| Gate | Outcome and acceptance | Status |
|---|---|---|
| I0 | Dated inventory, owner map, initial sizing and cost hypotheses | DOCUMENTED_BASELINE; measurement gaps remain |
| I1 | Regional service/SKU pricing, rendered requests/limits, measured usage, dependency graph, target HLD | **CRC_NAMESPACE_SEGMENTATION_DOCUMENTED / P95_AND_FULL_BOM_OPEN** |
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

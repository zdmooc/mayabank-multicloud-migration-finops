# MultiCloud Migration & FinOps — backlog

**Date:** 2026-10-09 | **Status:** ASSESSMENT_ONLY | **Cloud deployment:** NOT AUTHORIZED

| Gate | Outcome and acceptance | Status |
|---|---|---|
| I0 | Dated inventory, owner map, initial sizing and cost hypotheses | DOCUMENTED_BASELINE; measurement gaps remain |
| I1 | Regional service/SKU pricing, rendered requests/limits, measured usage, dependency graph, target HLD | **STATIC_EVIDENCE_PACK_READY / LIVE_METRICS_AND_FULL_BOM_OPEN** |
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

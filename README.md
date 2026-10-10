# MayaBank — MultiCloud Migration & FinOps

> **Status:** `ASSESSMENT_ONLY` | **Baseline:** 2026-10-09 | **Targets:** Microsoft Azure, AWS, Google Cloud
>
> This public, synthetic MayaBank engineering portfolio project is **not** a banking production environment and contains **no** real customer infrastructure.

## Purpose

Create one traceable decision and execution dossier for evaluating and progressively migrating selected existing MayaBank runtimes from local OpenShift CRC / Kubernetes Kind to managed cloud platforms:

- Azure: AKS first, with Azure Red Hat OpenShift (ARO) as an explicit alternative;
- AWS: EKS first, with Red Hat OpenShift Service on AWS (ROSA) as an alternative;
- Google Cloud: GKE first, with OpenShift Dedicated as an alternative where feasible.

The scope covers inventory, dependencies, workload resource sizing, migration waves, target architecture, indicative TCO/FinOps, risks, validation gates and evidence. **This repository does not own a new Kubernetes platform, duplicated Terraform modules, business application code, or the runtime configuration of existing services.**

## TradeOps GPU inference — local station vs Azure / AWS / GCP (2026-10-09)

**Canonical cost and option dossier:** [AI inference TCO — existing ZBook/portable/workstation versus Azure, AWS and GCP](finops/AI_INFERENCE_TCO_LOCAL_STATIONS_AZURE_AWS_GCP_2026-10-09.md). This consolidates all options from the October 9 discussion: RTX 3090/4090/5090 and GB10 local stations, previous mobile-workstation alternatives, GCP L4, AWS L4 and Azure T4/A10, **4 hours/day weekday vs daily** compute scenarios, storage/network/energy/TCO caveats, and inspected public Terraform repositories.

**Hybrid target assessment:** [TradeOps CRC + external GPU HLD](architecture/TRADEOPS_HYBRID_GPU_INFERENCE_HLD_2026-10-09.md). Keep the existing HP ZBook/OpenShift Local CRC for business workloads and the governed LiteLLM path; rent a GPU on demand or attach a dedicated Linux/NVIDIA workstation for inference. No GPU was purchased or deployed, cloud prices are **unverified planning inputs**, and Terraform remains owned by a qualified implementation repository per ADR-001.

## I1 October 10 CRC runtime observation

**Live instantaneous monitoring works:** `oc adm top` shows 1765m CPU (22%) and 18367Mi RAM (77%) for the CRC node. The original local collection warning came from an invalid `oc top` command; the collector now dispatches correctly. A [sanitized analysis](evidence/I1_CRC_LIVE_METRICS_2026-10-10.md) and [offline test](tests/test_local_collector_top_dispatch.sh) are available. These numbers are **not P95** and cannot directly validate production Cloud worker sizing.

## I1 — 10 October request-pressure evidence

New [sanitized request/allocatable evidence](evidence/I1_CRC_REQUEST_CAPACITY_2026-10-10.md): CRC 1 node / 7.80 allocatable vCPU / 23.02 GiB RAM, 149 Running and 3 Pending pods; Running regular-container requests **7,318m CPU and 23,267 MiB RAM**, or **93.82% CPU and 98.70% memory of node allocatable**. Including Pending gives 7,348m/23,457MiB (94.21%/99.51%), but Pending requests may not be scheduled. These are **declared requests**, not measured CPU/RAM load. PVC: 15 Bound, 52 GiB requested; actual used bytes and P95 are unknown. The new [safe local summary](scripts/summarize-local-inventory.py) reports aggregated resource pressure by namespace category only.

## First assessment

| Profile | Nodes | Total node vCPU | Total node RAM | Indicative persistent storage | Run schedule |
|---|---:|---:|---:|---:|---|
| Targeted demo | 2 | 8 | 32 GiB | 150 GiB | ~160 h/month |
| Portfolio integration | 6 | 24 | 96 GiB | 500 GiB | 24/7 |
| Illustrative HA target | 10 | 40 | 160 GiB | 1,500 GiB | 24/7 |

These are **planning profiles**, not proven capacity requirements, reference architectures for regulated production, or vendor quotes. The small profile runs selected workloads, not every repository at once. The HA profile is not HA-certified until zonal placement, stateful replication, backup/restore and failure tests are performed. Cloud control-plane, system-pod reserves, service limits and dedicated workloads may require additional capacity.

For inputs, method and pricing caveats see [capacity-planning](capacity-planning/) and [finops](finops/). Previously communicated cost figures are retained as **historical planning placeholders**, not validated regional prices.

## I1 partial static audit

**Gate:** `I1_STATIC_EVIDENCE_PACK_READY` / **I1 NOT CLOSED**. The static comparison now includes:

- [Manifest request ledger](capacity-planning/declared-workload-requests-2026-10-09.csv) for selected application components; requests are **not** actual utilization.
- [Manifest analysis and cautions](capacity-planning/I1_MANIFEST_ANALYSIS_2026-10-09.md).
- [Paris-region compute + AKS/EKS/GKE management price review](finops/PRICING_REVIEW_2026-10-09.md): secondary published VM prices + official published cluster rates; **not a full TCO or verified direct vendor quotation**.
- [I1 evidence status](evidence/I1_RETRIEVAL_STATUS_2026-10-09.md).
- [Local read-only collector](scripts/collect-local-inventory-readonly.sh), outputs ignored by Git pending review.
- [Historical P95 measurement recipes](capacity-planning/PROMQL_P95_RECIPES.md), **not run yet**.

## Sources and operating model

- [Repository scope](inventory/repository-scope.csv) distinguishes executable products, shared capabilities, specialists and references.
- [Observed local inventory](inventory/runtime-baseline-2026-10-09.md) records dated CRC / Kind evidence and separate source/config assumptions.
- [Cloud mapping](architecture/cloud-service-mapping.md) covers the provider-specific differences.
- [Ownership ADR](architecture/ADR-001-ownership-boundaries.md) avoids duplication with existing MayaBank repositories.
- [Backlog](BACKLOG.md) records gates from study to eventual deployment.
- [Instant Payments pilot](migrations/instant-payments/PLAN.md) is the proposed first workload.
- [Evidence template](evidence/EVIDENCE_TEMPLATE.md) prohibits unproven cloud runtime claims.

### Existing source-of-truth repositories

| Area | Existing owner |
|---|---|
| Portfolio governance / architecture decisions | `zdmooc/cadrage_202682030` |
| Cluster lifecycle, capacity, Terraform provider contracts | `zdmooc/k8s-openshift-cluster-factory` |
| Azure landing zone / Terraform / cloud patterns | `zdmooc/mayabank-azure-cloud-ai-platform` |
| Migration, cutover and rollback engineering | `zdmooc/openshift-migration-framework` |
| Shared Platform API, Operator and consumption contracts | `zdmooc/shared-platform-services-openshift` |
| GitOps specialist | `zdmooc/argocd-expert-pack` |
| First business pilot and service-specific manifests | `zdmooc/mayabank-instant-payments-resilience-platform` |

This repository **orchestrates** those owners. Cloud-specific IaC belongs in an existing qualified owner unless a separate, accepted ADR demonstrates a genuine new responsibility.

## Decision and deployment safety

1. **No paid cloud resources without explicit human approval of provider, subscription/project/account, region, estimated monthly cap and teardown plan.**
2. `terraform plan`, manifest rendering and price analysis are allowed only as non-mutating steps against sanitized inputs. No unattended `apply`, `destroy` or live Kubernetes writes.
3. No secrets, tokens, credentials, kubeconfig, real customer names, billing IDs, nonpublic details or Terraform state in this **public** repository.
4. CRC single-node or Kind multi-node evidence is not public-cloud, production, multi-AZ or disaster recovery evidence.
5. Make monthly operating cost and shutdown economics visible; tag all eventual resources, set budgets/alerts before deploying.

## Suggested qualification order

`I0 assessment -> I1 architecture & real pricing -> I2 IaC plan and readiness -> I3 AKS bounded pilot -> I4 EKS / GKE portability -> I5 workload waves -> I6 production-like HA qualification`.

**Current gate:** `I0_INITIAL_REPOSITORY_BASELINE_DOCUMENTED` plus `I1_STATIC_EVIDENCE_PACK_READY`; complete current per-pod usage, official direct regional SKU quotes, complete bill of materials and cloud runtime evidence are pending.

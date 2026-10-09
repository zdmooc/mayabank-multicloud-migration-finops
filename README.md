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

## First assessment

| Profile | Nodes | Total node vCPU | Total node RAM | Indicative persistent storage | Run schedule |
|---|---:|---:|---:|---:|---|
| Targeted demo | 2 | 8 | 32 GiB | 150 GiB | ~160 h/month |
| Portfolio integration | 6 | 24 | 96 GiB | 500 GiB | 24/7 |
| Illustrative HA target | 10 | 40 | 160 GiB | 1,500 GiB | 24/7 |

These are **planning profiles**, not proven capacity requirements, reference architectures for regulated production, or vendor quotes. The small profile runs selected workloads, not every repository at once. The HA profile is not HA-certified until zonal placement, stateful replication, backup/restore and failure tests are performed. Cloud control-plane, system-pod reserves, service limits and dedicated workloads may require additional capacity.

For inputs, method and pricing caveats see [capacity-planning](capacity-planning/) and [finops](finops/). Previously communicated cost figures are retained as **historical planning placeholders**, not validated regional prices.

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

**Current gate:** `I0_INITIAL_REPOSITORY_BASELINE_DOCUMENTED`; actual price quotes, complete live per-pod utilization and deployment runtime evidence are still pending.

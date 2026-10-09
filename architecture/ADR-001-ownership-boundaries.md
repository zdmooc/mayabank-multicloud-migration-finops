# ADR-001 — A cross-cloud assessment owner, no new platform duplication

**Date:** 2026-10-09 | **Status:** ACCEPTED_FOR_ASSESSMENT

## Decision

The new repository owns only cross-cloud **inventory, capacity planning, costs, architecture options, migration wave choices, controls, test plans and evidence**. It is not an OpenShift platform, monorepo, Terraform implementation owner or business application repository.

| Domain | Implementation owner | Responsibility here |
|---|---|---|
| Portfolio governance | `cadrage_202682030` | Track decisions and link to source |
| Cluster factory / lifecycle | `k8s-openshift-cluster-factory` | Define capacity targets / required evidence |
| Azure landing zone | `mayabank-azure-cloud-ai-platform` | Qualify AKS plan, refer to Azure IaC |
| Migration/cutover | `openshift-migration-framework` | Wave order and cutover gates |
| Shared Operator/OIDC/OTel | `shared-platform-services-openshift` | Consumer and integration contract |
| GitOps | `argocd-expert-pack` + application owner | Reconciliation evidence |
| Apps and stateful stores | Individual product repositories | Dependencies, no duplicated manifests |
| Multi-cloud TCO/decision dossier | **This repository** | Study owner |

No default global PostgreSQL, Kafka or MinIO consolidation. Cloud-specific IaC remains with existing owners until evidence and an ADR justify extraction. No business/source code is copied.

## Consequences

No platform Big Bang. Cross-repo provenance and runtime evidence are mandatory; no "cloud ready" claims from static validation. Creation of common reusable services requires a concrete consumer.

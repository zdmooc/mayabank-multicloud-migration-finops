# First pilot — Instant Payments from CRC to Azure AKS

**Status:** PLANNED_ONLY / NOT_DEPLOYED / NO_CLOUD_SPEND_APPROVED
**Source owner:** `zdmooc/mayabank-instant-payments-resilience-platform`
**Orchestration:** this repository
**Cluster & Azure platform implementation:** existing `k8s-openshift-cluster-factory` / `mayabank-azure-cloud-ai-platform` owners
**Migration engineering:** `openshift-migration-framework`
**Shared platform contracts:** `shared-platform-services-openshift`

## Why this pilot

Instant Payments has a bounded CRC runtime proof, product-owned manifests, PostgreSQL and Kafka-compatible messaging, OAuth/OIDC and GitOps. It is suitable for proving cloud compatibility **without claiming real bank integration or regulated production**.

## Gates

### P0 — Read-only preflight

- [ ] Read owner repository current `main` and canonical GitOps overlays.
- [ ] Render intended workload replicas, resource requests/limits and dependencies (all namespace-scoped).
- [ ] Compare `Route`, SCC, registry, PVC, DNS, network policies and secrets with AKS APIs.
- [ ] Size PostgreSQL databases, Kafka, Keycloak/Kong, OpenTelemetry and product observability separately.
- [ ] Check payment invariant `UNKNOWN != FAILED` and replay/idempotency test fixtures.
- [ ] Check external integrations are simulations with synthetic data.

### P1 — Architecture & budget

- [ ] Choose France Central region and eligible instance families *only after official verification*.
- [ ] HLD / risk and threat review; VNet/private ingress, DNS, workload identity, registry, encrypted persistence.
- [ ] Decide if Kafka/DB run in cluster or as managed services, including consistency and backup/restore implications.
- [ ] Estimate minimum and maximum cost, define explicit stop and spending budget alert.
- [ ] Create IaC changes with real owner (do not copy modules into this repository).

### P2 — Controlled execution (requires explicit approval)

- [ ] State account/subscription, region, resources permitted, approval identity/time, max cost and rollback.
- [ ] Provision only the approved ephemeral AKS lab.
- [ ] Deploy platform shared contracts and one application slice with owned GitOps overlays.
- [ ] Verify API + JWT/OIDC, payment E2E including duplicate/retry/unknown/reconciliation, event trace, storage consistency.
- [ ] Capture actual CPU/RAM, disk, networking and billed costs.
- [ ] Exercise drift/self-heal, planned rollback and failure recovery; do not extrapolate HA.

### P3 — Teardown/closure

- [ ] Backup synthetic evidence if needed, teardown all approved resources.
- [ ] Verify no residual PVC/disk/snapshot/LB/IP/NAT/registry resource continues to bill.
- [ ] Archive sanitized evidence with commit SHA and timestamps.
- [ ] Update cross-cloud portability matrix for EKS and GKE.

**Forbidden:** real banking data, unattended cloud creation, public admin endpoints, uncontrolled duplicate transactions and production/HA claims without multinode fault tests.

# I1 — Target architecture alternatives (HLD v0.1)

**Date:** 2026-10-09 | **Status:** OPTIONS_DOCUMENTED / NOT_APPROVED_FOR_DEPLOYMENT

## Objective

Compare **one bounded Instant Payments pilot at a time** on Azure AKS, AWS EKS, and Google GKE. ARO, ROSA and OpenShift Dedicated are separate compatibility/licensing alternatives. Never assume three simultaneously running, permanent Cloud platforms.

## Target logical design

```text
MayaBank application Git / CI --> tested signed image --> cloud registry
  GitOps desired state             |
             |                     v
  Approved cloud / one region / private Kubernetes network
     managed cluster control plane + system pool + app worker pool
       --> TLS Ingress/API gateway --> Instant Payments stateless APIs
                       |                  |           |
                   Keycloak/OIDC     PostgreSQL   Kafka outbox/inbox
                            \            |          /
                             --> Shared OTel contract --> monitoring
                   Workload Identity --> secrets + key management
                   Tagged resources / budget / teardown controls
```

This is a logical placement *proposal*, not a designed CIDR/routing plan or deployable Terraform.

## Technical boundaries

| Topic | Recommendation | Pending proof |
|---|---|---|
| Worker pool | 2x4vCPU/16Gi for rotating demo, 6x for integration | Allocatable and current P95 usage |
| System pool | Separate pool if provider or workload needs it | Node inventory and full BOM |
| Payment API & S2S | Keep deployed product manifests and OAuth/OIDC contracts | JWT positive/negative E2E |
| Database | Keep product boundaries; evaluate managed vs lab PostgreSQL | Consistency, snapshot/restore, bill |
| Messaging | Dedicated Kafka-compatible path for correctness tests | Outbox/replay/offset/risk control |
| IAM/API Edge | Keep Shared OIDC and Kong contract semantics | Token issuer, network, TLS |
| GitOps/Operator | Keep ownership of Shared Platform/Argo | Kubernetes permissions and CRD compatibility |
| Data | Synthetic fixtures only | Storage growth/IOPS/RPO/RTO |
| Observability | OTel contract, product observability until equivalent shared exists | Business metrics, tracing, ingestion costs |
| Network | Private access by default, least privilege ingress and egress | DNS/LoadBalancer/NAT/WAF cost and architecture |

## Provider adaptations

- OpenShift Route --> Kubernetes Ingress or Gateway API where supported; verify TLS behavior.
- SCC --> provider-compatible PSS, Admission and runtime SecurityContext with negative tests.
- BuildConfig and ImageStream --> external CI/registry images pinned to immutable digest.
- OLM and CapabilityConsumption --> controller compatibility, CRD installation and RBAC must be independently tested.
- StorageClass/PVC zones --> verify binding and zone placement, especially for stateful databases.
- Cloud IAM --> workload identity to secrets manager, not a direct copy of local static identities.
- Native managed Kafka/Storage is **not** automatically contract-compatible with current clients.
- Local Ollama does not imply free/included cloud inferencing; create separate model cost lane.

## HA and budget truth

10 workers spread over zones does **not** imply HA. Product DB and messaging replication, failover tests, pod scheduling, PV zone binding and backup/restore must support documented RTO/RPO. All profiles are illustrative until workload metrics and failure evidence.

**No paid deployment is authorized.** HLD acceptance requires measured workload demands, full regional BOM, data and security review, cost cap, Terraform plan review and explicit human approval.

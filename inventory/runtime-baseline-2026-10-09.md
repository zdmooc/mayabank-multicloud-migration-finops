# Historical local runtime baseline — audited 2026-10-09

This is a **document review**, not an interactive `oc`/`kubectl` session. Source of truth: private `cadrage_202682030/portfolio/LOCAL_CRC_RUNTIME_INVENTORY_2026-10-03.md` and `RUNTIME_DEPLOYMENT_MATRIX.md`. Do not confuse different snapshots.

## CRC — snapshot dated 2026-10-03

- Single node OpenShift Local 4.22.7 / Kubernetes 1.35.6; configured **8 vCPU / ~32 GiB RAM**.
- At that snapshot, CPU ~38%, memory ~70%; disk **114/200 GiB** used. These are dated measurements, not P95 sizing.
- Active application/platform areas: Instant Payments, Maya Freelance, API Management, IBM MQ, Decision AI, TradeOps, Shared Platform, Keycloak. Historical Wero `wero-poc` was scale 0.
- Reported active databases: eight PostgreSQL and one Qdrant. Historical MongoDB read model did not run then.
- Kafka (Payments), Redpanda (TradeOps), and IBM MQ specialized broker.
- Multiple local observability components; do not consolidate without functional replacement proof.
- Subsequent evidence in canonical matrix (2026-10-07) supersedes the snapshot's earlier errors/status.

## Selected declared Kubernetes resources — NOT measured consumption

| Source | Declaration |
|---|---|
| `mayabank-instant-payments-resilience-platform/gitops/base/workloads.yaml` | payment-orchestrator, consumer-psp and acceptor-service each 2 replicas, each replica requests 50m CPU / 192 Mi RAM in base; verify actual overlay |
| `mayabank-ibm-mq-native-ha-openshift-eda-platform/deploy/local-crc/mq.yaml` | 1 MQ, requests 500m CPU / 1 Gi RAM, 5 Gi PVC |
| `mayabank-ibm-odm-ai-decision-architecture/deploy/openshift/10-workload.yaml` | 1 decision-api, requests 100m CPU / 128 Mi RAM |
| `TradeOps-GenAI-Integration/infra/openshift/base/resourcequota.yaml` | Namespace request quota up to 6 CPU / 10 Gi memory; **not** actual usage |
| `TradeOps-GenAI-Integration/infra/helm/tradeops/values-crc.yaml` | Local small-service requests; do not substitute base Helm values or quota for runtime observation |

## Separate Kind Data Lakehouse — H3 evidence 2026-10-06

One control-plane and two workers, **3 Ready nodes / 45 healthy or completed pods / 7 Bound PVC / 2 Synced & Healthy Argo Apps**. Kafka/Strimzi, Spark, RustFS S3-compatible, Iceberg/Polaris, Trino, Jupyter, monitoring. Kafka RF=1 and Polaris memory-only: not HA.

**Important:** do not sum CRC configured VM capacity and Kind node count as measured simultaneous usage. Record active workloads, bin-packing, controller and system reserves, stateful footprint, logs, backups and egress separately.

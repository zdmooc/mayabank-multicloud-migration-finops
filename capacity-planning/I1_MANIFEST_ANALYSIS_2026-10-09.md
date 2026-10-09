# I1-S — Resource request extraction from public GitHub manifests

**Date:** 2026-10-09 | **Status:** STATIC_MANIFEST_ANALYSIS_COMPLETE / LIVE_USAGE_NOT_PROVEN

## Results — not cluster consumption

The [CSV ledger](declared-workload-requests-2026-10-09.csv) records traced requests for a subset of key applications. Aggregations follow declared base manifests and selected Kind/CRC Helm values. **Do not interpret this as all pods or a live deployment**, or translate resource requests directly into P95 load.

| Application/stack | CPU request subtotal | Memory request subtotal | Boundary |
|---|---:|---:|---|
| Instant Payments base, 5 services × 2 replicas | **500m** | **1,920 Mi** | Does not count PostgreSQL/Kafka/Keycloak/Kong, frontend, Camel, MongoDB, observability |
| TradeOps CRC Helm, 17 default-enabled components | **645m** | **1,880 Mi** | Overlay assumed; excludes extra AI Access/LiteLLM, Ollama and dynamic D-090/D-092 |
| IBM MQ single instance | **500m** | **1,024 Mi** | MQ Native HA would be substantially different |
| Decision AI decision-api | **100m** | **128 Mi** | No licensed IBM ODM runtime |
| Maya Freelance dashboard+n8n+Postgres lab | **250m** | **736 Mi** | No data IOPS/backups/scale |
| European Processing one OpenShift API | **100m** | **256 Mi** | Other source service directories not counted as deployed |
| Data Lakehouse selected Kind core + monitoring | **1,430m** | **4,512 Mi** | Spark/History, Jupyter, Strimzi operator, Argo CD, CNI, DNS not counted |
| Shared OTel Collector | **50m** | **128 Mi** | Not full Shared Platform |

Sum of these explicitly **sampled, non-deduplicated, mixed-environment** requests: **3,575m CPU / 10,584 Mi RAM**. It is **not** a usable cross-cloud total because selected source profiles may differ from real runtime; dependencies omitted; some workloads run on separate clusters and snapshots. More complete rendering is required.

## Risk and packing implications

1. **Requests are much smaller than physical cluster allocations** because Kubernetes allocatable reserves, control components, peak/OOM protection, data services, autoscaling, node upgrade and topology placement dominate planning.
2. **2 workers × 4 vCPU/16 GiB is a bounded demo, not the complete portfolio**. System pool, Kafka/MQ, log collectors and databases may exhaust allocatable capacity. No simultaneous-all claim.
3. **6 workers × 4 vCPU/16 GiB is only a proposal**, not justified by measured P95. Cluster/namespace quotas do **not** equal actual demand. Check overcommitted cpu requests and per-zone placement.
4. **10 workers** alone cannot demonstrate HA. Kubernetes stateful replication, PV zone binding, PostgreSQL/Kafka recovery, network paths, pod disruption budget and tested failure behavior are required.
5. **Not all application repositories require continuous nodes.** Some are document/reference only or CI synthetic.
6. **AI** inference is a separate cost profile if an LLM endpoint or GPU is needed; local Ollama CPU model is not included.
7. MongoDB image failure from older CRC snapshots must not be promoted to current runtime status without rechecking.

## Work to finish I1

- Run local read-only script, inspect before adding sanitized artifacts.
- Render exact overlays with current chart versions and lifecycle states for active pods.
- Obtain 7–30 days CPU/memory trend (peak, P95, saturation), plus IOPS/network and storage used bytes.
- Inventory number of control-plane, system pools and allowed zones per provider.
- Expand bill of materials and verify each service price from official cloud calculators.

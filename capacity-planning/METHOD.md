# Capacity planning method

Per environment and workload: render Kustomize/Helm overlays; count active `replicas × requests` separately from limits and actual P95/P99 usage; collect pod placement, pending and autoscaling status. From each candidate node's **allocatable** CPU/RAM subtract kube-system/CNI/ingress/telemetry/DaemonSets, failover and upgrade margins. Size worker count on max(CPU pressure, RAM pressure) then validate anti-affinity, zones, PVC binding and HA constraints. Stateful MQ, PostgreSQL, Kafka, object storage and Data Lakehouse need separate volume growth, latency, IOPS, retention, replication and recovery design.

Baseline [YAML](scenarios.yaml) is an **architecture hypothesis** rather than observed resource demand. The 8 vCPU / 32 GiB local CRC configured footprint is not equivalent to a managed multi-cloud bill of materials. The 2×4-vCPU lab is **not** meant for all simultaneous applications and may require turning off workloads.

**Inputs missing:** current per-workload requests/limits and P95 utilization, load profiles, used persistent bytes/IOPS, egress, exact regions/SKUs, licensing, backups and non-Kubernetes managed-service charges.

**No production claim:** 10 workers ≠ demonstrated HA without a three-zone topology, stateful replication, recovery/fault tests and supported SLAs.

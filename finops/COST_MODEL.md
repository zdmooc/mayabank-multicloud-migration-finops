# FinOps — pricing model and billing controls

**Status:** HISTORICAL_ASSUMPTIONS_ONLY, no region/SKU-specific quote verified.

This repository retains the figures communicated during the initial 2026-10-09 conversational sizing assessment as a **working hypothesis**, not as vendor prices or a purchasing recommendation. See [illustrative budget](illustrative-budget-baseline.csv). Costs can vary significantly with region, selected VM families, commitments, node count, actual hours, data services, licensing and transfer.

## Cost calculation contract

For each provider + region + profile, collect official dated SKUs and calculate monthly USD **before tax**:

`COST = worker_vCPU_RAM_compute + managed_control_plane + persistent_volumes + snapshots_backup + load_balancer + public_IP_NAT + logging_metrics + registry + managed_databases + messaging + storage_API_requests + data_egress + support_licenses + model_API_GPU`.

The costs from the first study are **not rebuilt from priced SKUs**. Do not call them a real regional quote. Do not compare AKS/EKS/GKE or ARO/ROSA/OpenShift Dedicated using only one generic hourly node rate.

## Required inputs

| Item | Minimum evidence before approval |
|---|---|
| Region | Provider region and zone placement explicitly recorded |
| Workers | Actual SKU, architecture, allocatable RAM/CPU, hourly price, node count |
| Cluster | Free vs paid tier, hourly control-plane/cluster fees, support |
| Operation | Hours/month; on-off scheduling and residual storage/control-plane costs |
| Persistence | GB-month, disk type, IOPS/throughput, snapshot and replication |
| Network | LB, NAT gateway, public IP, private endpoint, cross-AZ and Internet egress |
| Services | PostgreSQL, Kafka, IBM MQ license/support, object storage, IAM, monitoring |
| AI | Cloud LLM token price or GPU inference instance; local Ollama is not a zero-cost cloud service |
| Governance | Budget alarm thresholds, tagging, currency conversion/date and tax |
| Validation | Official pricing URL, calculation date, selected discount commitment |

## Workload schedules

- `targeted-demo`: about 160 hours of active worker consumption/month, but **not all services stop being billed** during off-hours (disks, IPs, cluster fees, backups etc.).
- `portfolio-integration`, `illustrative-ha`: approximately 730 hours/month.
- Cost of 3 independent clusters, one on each provider, is not the same as comparing 3 mutually exclusive migration options.

## Policy

No deployment or budget approval from this table alone. The exact regional BOM, official calculator links and approval are prerequisites for I2/I3.

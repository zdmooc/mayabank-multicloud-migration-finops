# I1 — First region-specific **compute + cluster management only** price review

**Checked:** 2026-10-09. **Status:** PARTIAL_EXTERNAL_EVIDENCE. **Not a complete TCO or official 3-provider SKU quotation.** USD, before tax, pay-as-you-go Linux, no reservation or Spot, no credits.

## Source confidence

1. **Verified published provider cluster-management rate:** Azure AKS Standard, AWS EKS version under standard support, Google GKE Standard **$0.10/cluster-hour**. See:
   - https://learn.microsoft.com/en-us/azure/architecture/aws-professional/eks-to-aks/cost-management
   - https://aws.amazon.com/eks/pricing/
   - https://cloud.google.com/kubernetes-engine/pricing
2. **Secondary public comparator for regional compute:** Holori listed on-demand rates for approximately 4-vCPU/16-GiB VMs, **not official direct Azure/AWS/GCP API quotes**. These are temporary cross-vendor illustrations and need API/calculator validation before I1 closure.
   - Azure France Central ¦Standard_D4as_v5¦: **$0.2020 per worker-hour** (Holori regional list updated 2026-09-10): https://calculator.holori.com/azure?region=francecentral
   - AWS Paris ¦m6i.xlarge¦: **$0.2240 per worker-hour** (Holori 2026-09-10): https://calculator.holori.com/aws/ec2/m6i.xlarge?os=Linux&region=eu-west-3&upfront=no-upfront
   - Google Paris ¦n2-standard-4¦: **$0.2253 per worker-hour** (Holori 2026-09-30): https://calculator.holori.com/gcp/vm/n2-standard-4?region=europe-west9
3. Official direct VM/instance API quote still **MISSING**:
   - Microsoft Azure Retail Prices API documentation: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices
   - AWS official EC2 on-demand prices: https://aws.amazon.com/ec2/pricing/on-demand/
   - Google Cloud public Catalog API requires an API key: https://docs.cloud.google.com/billing/v1/how-tos/catalog-api

## Computed subtotal with 1 cluster

| Scenario | 2/6/10 workers | Azure (USD/month) | AWS | Google |
|---|---:|---:|---:|---:|
| targeted-demo (160 active hours) | 2 | $80.64 | $87.68 | $88.10 |
| portfolio-integration (730 h) | 6 | $957.76 | $1,054.12 | $1,059.81 |
| illustrative-ha (730 h) | 10 | $1,547.60 | $1,708.20 | $1,717.69 |

**Compute + cluster only**: ¦workers × worker_hourly_price × hours + 0.10 × cluster_active_hours¦. Rounded to cents; Google node-hourly rate has four decimal places. Google GKE monthly cluster-management credit up to **$74.40 per billing account**, where eligible, is excluded and must not be assumed; a regional GKE cluster is not eligible for this free tier. Azure AKS Free tier is separate (no SLA) and not assumed here. AWS extended Kubernetes support is **$0.60/h** rather than $0.10/h.

**Crucial demo teardown assumption:** 160 hours means **cluster and workers removed outside sessions**, not merely ¦kubectl scale --replicas=0¦. If the managed cluster remains active for 730 h, its management fee may be **$73 instead of $16**. Persistent disks/registry/snapshots/network IPs may accrue charges while workers are off.

## Costs not included in this subtotal

- Persistent disks/PVC and snapshots, backups, multi-AZ replication and object storage.
- Network private endpoints, LB, WAF, NAT, public IP, cross-AZ traffic and Internet/cloud-to-cloud egress.
- PostgreSQL, Kafka/Redpanda, MQ licensing/support and stateful HA, Keycloak/Kong if moved to managed offers.
- Log/metrics ingestion and retention, source-control CI, private registries and image storage.
- Ollama replacement via model hosting, GPU/AI, tokens and rate-based inference.
- Tax, FX, support, HA failover extra workers, system node pool, subscription discounts, region quotas.

The previously communicated **all-in illustrative totals** stored in ¦illustrative-budget-baseline.csv¦ are **not validated**, should not be mixed with this new subtotal and must not be used as a spending authorization. They may even be insufficient depending on paid managed-service choices. See [SKU sources](region-sku-price-sources-2026-10-09.csv) and [subtotal calculations](compute-cluster-subtotal-2026-10-09.csv).

## I1 remaining actions

- Official regional SKU live pricing for all three clouds.
- Monthly full BOM and cost calculator: node system pool, disks, DB, messaging, LB/NAT/egress, backup, logs, support.
- Actual CRC and Kind usage and rendered workload claims.
- Versioned price evidence and two independent pricing checks before approving spending.

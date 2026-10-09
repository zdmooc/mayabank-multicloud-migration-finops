# Cloud provider mapping — options, not selected SKUs

| Capability | Azure | AWS | GCP |
|---|---|---|---|
| Kubernetes | AKS | EKS | GKE |
| OpenShift alternative | ARO | ROSA | OpenShift Dedicated (availability to verify) |
| Registry | Azure Container Registry | ECR | Artifact Registry |
| Private networking | VNet/Private Link | VPC/PrivateLink | VPC/Private Service Connect |
| Load balancing | Azure LB/App Gateway | ALB/NLB | Cloud Load Balancing |
| Workload identity | Entra Workload ID | EKS Pod Identity / IRSA | Workload Identity Federation |
| Secrets | Key Vault | Secrets Manager | Secret Manager |
| Managed PostgreSQL option | Azure Database for PostgreSQL | RDS PostgreSQL | Cloud SQL for PostgreSQL |
| Eventing | Event Hubs Kafka compatibility or dedicated Kafka | MSK or dedicated Kafka | Kafka managed/self-hosted based on qualification |
| Object storage | Blob Storage/ADLS | S3 | Cloud Storage |
| Logs/metrics | Azure Monitor | CloudWatch | Cloud Monitoring |
| Cloud budgets | Azure Cost Management | AWS Budgets | Cloud Billing Budgets |

First indicative regional comparison: Azure `francecentral`; AWS `eu-west-3`; GCP `europe-west9`. **No deployment region approved.** Verify local availability of services, support and price.

Avoid naïve equivalence: Azure Event Hubs ≠ generic Kafka feature parity, Azure Blob ≠ fully compatible S3 API, and hosted model inference ≠ local Ollama. IBM MQ Native HA has support/license/storage constraints outside generic worker costs. Market Access ultra-low-latency hot paths are not assumed cloud-portable.

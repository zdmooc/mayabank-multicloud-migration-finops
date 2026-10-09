# Public repository safeguards and financial approval policy

1. **Study-only default**. No automatic paid resource creation; no pipelines that run `terraform apply` or equivalent.
2. This repository is **public**. Never commit credentials, GitHub tokens, cloud subscription/account/project IDs, customer network topology, financial records, external integrations, user data, real client names or Terraform state.
3. Inspect the data classification of any dataset before uploading it to a Cloud. Only synthetic fixtures in first pilot.
4. **Written deployment approval must identify**: responsible owner, provider, subscription/account/project (in a secure channel), region, service types, max spend, expiry/teardown and audit record.
5. Set cost budgets, alerts and tagged ownership before activating fee-bearing resources.
6. Encrypt storage and transport; preserve IAM least privilege, egress restrictions, audit logging and workload identities.
7. Keep rollback and clean teardown, including snapshots, NAT, static IPs, log storage and load balancers.
8. Do not equate three-zone nodes with qualified HA, and do not assert multi-region DR without observed tests.
9. Protect payment correctness and idempotency independently of cloud/platform deployment success.
10. Reevaluate proprietary IBM MQ and Red Hat OpenShift licensing/support, GPU hosting and rate-based AI costs explicitly.

**No cloud resource has been created by this repository's bootstrap.**

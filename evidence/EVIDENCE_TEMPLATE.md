# Multi-cloud evidence record template

Copy this template **only after a real, bounded observation**.

| Field | Value |
|---|---|
| Date/time (UTC) | PENDING |
| Provider and region | PENDING |
| Account reference (sanitized) | PENDING |
| Workload/repo/commit SHA | PENDING |
| Scenario/profile/active schedule | PENDING |
| Kubernetes control-plane/runtime version | PENDING |
| IaC owner and commit SHA | PENDING |
| Manifest/render SHA | PENDING |
| Architecture/ADR approvals | PENDING |
| Budget alert/budget approval | PENDING |
| Deployment proof | NOT_EXECUTED |
| API/auth/network evidence | NOT_EXECUTED |
| Correctness/idempotency negative case | NOT_EXECUTED |
| Backup/restore or rollback test | NOT_EXECUTED |
| P95 CPU/RAM and volumes | NOT_MEASURED |
| Incurred/estimated provider charges | NOT_MEASURED |
| Cleanup verification and residual charges | NOT_EXECUTED |
| Failures, limits, open risks | PENDING |
| Gate decision | NOT_APPROVED |

Allowed vocabulary: `REFERENCE_ONLY`, `STATIC_VALIDATED`, `CI_VALIDATED`, `KIND_RUNTIME_PROVEN`, `CRC_RUNTIME_PROVEN`, `CLOUD_RUNTIME_PROVEN`, `MULTIZONE_PROVEN`, `PRODUCTION_REFERENCE`. Do not promote without its corresponding evidence.

No secrets, billing identifiers, customer data, terraform state, tokens, private endpoints or raw support attachments in a public repository.

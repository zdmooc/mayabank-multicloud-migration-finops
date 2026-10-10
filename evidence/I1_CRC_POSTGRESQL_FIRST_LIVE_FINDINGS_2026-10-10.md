# CRC PostgreSQL — first local audit findings, 2026-10-10

## Scope and proof class

Source: operator-provided terminal outputs of `python scripts/audit-crc-postgresql-readonly.py` from the local Windows HP / OpenShift Local CRC 4.22.7, stored only under ignored `evidence/local/private-postgresql-20261010T102502Z`. This report is manually transcribed aggregate/resource metadata, **not independent direct CRC access** and **not historical workload sizing**.

The audit had succeeded despite a **separate Windows-only tempfile cleanup test failure**: in `test_postgresql_readonly_audit.py`, the current working directory was restored after the `TemporaryDirectory` context manager tried to delete it. Reported WinError 32/5 is a Windows file-lock error on the test temp folder, **not** a PostgreSQL or Kubernetes error. Patch: restore CWD **before** tempfile cleanup. GitHub Linux CI success does not by itself prove the operator's Python 3.14 Windows run succeeds; a local re-run is required.

## Validated counts and snapshot

- `WORKLOAD_COUNT=9`; `DESIRED_REPLICAS=8`; `READY_REPLICAS=8`; 8/8 running PostgreSQL containers matched in `oc adm top`.
- **Single-sample CPU usage** sum 38m, CPU requests sum 575m.
- **Single-sample memory usage** sum 301MiB, memory requests sum 1408MiB.
- One PostgreSQL container, Tekton Results, has 0 CPU and memory requests but reports 1m and 34MiB usage; zero requests do **not** mean zero usage.
- Eight declared Bound/PV-Retain PVC attachments (7 active plus 1 legacy Wero), sum **18GiB requested**, not actual bytes used.
- `tradeops/postgres` has `NONE_DECLARED` for PVC after workload template and running Pod volume inspection. The exact backing storage is still **unproven**; data **may** be ephemeral, but cannot conclude without inspecting the mounts, StatefulSet volumeClaimTemplates and actual container filesystem. **Do not restart or roll out TradeOps** until persistence has been assessed.
- Legacy `wero-poc/postgresql` remains SCALE0. Its CSI hostpath directory measures 64M but has not been consistently backed up or restore-tested.

## Measured per workload

| Namespace | Workload | Desired/Ready | CPU request / observed (m) | RAM request / observed (MiB) | PVC claim request |
| --- | --- | --- | --- | --- | --- |
| instant-payments-local | postgresql-acceptor | 1/1 | 25 / 2 | 128 / 36 | 1Gi |
| instant-payments-local | postgresql-consumer | 1/1 | 25 / 2 | 128 / 36 | 1Gi |
| instant-payments-local | postgresql-payments | 1/1 | 50 / 4 | 256 / 70 | 2Gi |
| maya-freelance | postgres | 1/1 | 100 / 7 | 256 / 40 | 5Gi |
| mayabank-mq-local | payments-db | 1/1 | 100 / 4 | 256 / 16 | 2Gi |
| keycloak-system | postgresql | 1/1 | 250 / 8 | 256 / 34 | 5Gi |
| openshift-pipelines | tekton-results-postgres | 1/1 | 0 / 1 | 0 / 34 | 1Gi |
| tradeops | postgres | 1/1 | 25 / 10 | 128 / 35 | NONE_DECLARED |
| wero-poc | postgresql | 0/0 | 0 / NA | 0 / NA | 1Gi |

Resources are requests and a momentary sample only. Do not use this snapshot as production performance, P95, memory peak or financial rightsizing evidence.

## Consumers inferred from configuration, not measured network sessions

- `CANDIDATE_SVC_LINKS=12`: **9 TradeOps services** (agent-controller, genai-api, market-data, mcp-server, notifier, paper-oms, rag-api, risk-engine, workflow-api) mapping `POSTGRES_HOST` to the Service selecting `tradeops/postgres`, plus `maya-dashboard` to `maya-freelance/postgres`, `tekton-results-api` to Tekton Results PostgreSQL, and Keycloak to `keycloak-system/postgresql`.
- `UNRESOLVED_CONNECTION_VARIABLES=24` counts variable-level configuration indications, including database name/user/port variables and `envFrom`. This is **not 24 applications, 24 failures or 24 database connections**.
- Instant Payments: DB URLs are unresolved by design without extracting potentially sensitive configuration; 5 application candidates show DB-related variable names (acceptor-service, consumer-psp, demo-cockpit, payment-orchestrator, reconciliation-service), but no independent connection proof. Maya n8n is also unresolved.
- No PostgreSQL SQL queries, session counts, connectivity checks, config values from Secret/ConfigMap, or measured disk-used for other PVCs were collected.

## Prioritized next steps

1. **P0 — TradeOps persistence:** inspect only metadata for StatefulSet volumeClaimTemplates, `spec.template.spec.volumes`, pod volumes and database container volumeMounts; do not disclose Secret values or start/stop workloads.
2. **P1 — DB-dependent apps:** map DB URL references via config sources under confidentiality controls, without exporting passwords or credentials. Current links are Service label configuration evidence, not actual SQL.
3. **P1 — Tekton requests:** document missing requests and assess operational safeguards under representative load before changing anything.
4. **P2 — FinOps:** gather a time series (7–30 days where practical), PostgreSQL PVC used bytes and backup/restore verification before considering consolidation or migration.
5. **P2 — Wero:** preserve historical CSI PV until a validated backup/restore exists; maintain SCALE0/NO_DELETE.

Decision: **NO DATABASE SCALE-DOWN, MIGRATION OR DELETION AUTHORIZED** by this snapshot.

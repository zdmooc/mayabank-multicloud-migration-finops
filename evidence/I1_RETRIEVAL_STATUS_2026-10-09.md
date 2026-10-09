# I1 external/internal evidence coverage — 2026-10-09

| Evidence | Status | Follow-up |
|---|---|---|
| Existing MayaBank main repo inventory | GITHUB_REVIEWED | Track active version/commit |
| CRC single node baseline from October 3 | HISTORICAL_OBSERVATION_REVIEWED | Refresh read-only |
| Data Lakehouse Kind H3 snapshot | HISTORICAL_OBSERVATION_REVIEWED | Refresh read-only |
| Selected workload requests/limits | STATIC_GITHUB_MANIFESTS_REVIEWED | Render specific overlays and latest active deployments |
| TradeOps effective CRC Helm requests | APPROXIMATE_TEMPLATE_MERGE | Must render Helm chart and resolve dynamic overlays |
| Live workload CPU/RAM | NOT_COLLECTED | Run local CLI; collect safe metrics |
| 7/30-day P95 | NOT_COLLECTED | Prometheus trend or equivalent |
| PVC used bytes / IOPS | NOT_COLLECTED | Pod filesystem + storage stats |
| Azure/AWS/GCP control plane published price | OFFICIAL_PUBLIC_DOCUMENTATION_VERIFIED | Confirm plan tier and applicability |
| Azure/AWS/GCP Paris compute 4cpu/16Gi rates | SECONDARY_COMPARATOR_REFERENCE | Confirm via official regional API/calc |
| Complete all-in BOM price | NOT_AVAILABLE | Network/data/OS/licenses/snapshots/AI |
| Cloud deployment / HA/DR tests | NOT_EXECUTED | Explicit future approval required |

**Gate:** ¦I1_STATIC_EVIDENCE_PACK_READY¦; **I1 not CLOSED**, cost and live capacity gates outstanding.

# I1 — CRC resource request segmentation: OpenShift prefix vs other namespaces

**Date:** 2026-10-10. **Evidence class:** LOCAL_READ_ONLY_CSV_AGGREGATES_USER_REPORTED / NOT_RAW_CSV_AUDITED.

The operator refreshed the repository locally by `git pull --ff-only` up to commit prefix `773a9b2` and ran:

```bash
python scripts/summarize-local-inventory.py evidence/local/private-20261010T081041Z
```

All data below are **numeric stdout from the user's locally executed safe summarizer**. Neither the original CSV files nor the live cluster has been inspected remotely. The collector generated the source CSV files at 2026-10-10 08:10 UTC.

## 1. Inventory and scheduler pressure

| Metric | Value |
|---|---:|
| CRC nodes | 1 |
| Node allocatable | 7.80 vCPU / 23.02 GiB RAM (rounded) |
| All pod records | 270 |
| Running / Pending / Succeeded / Failed | **149 / 0 / 92 / 29** |
| Containers in active Running/Pending pods | 217 |
| Active CPU requests | **7,318m (93.82% of node allocatable)** |
| Active RAM requests | **23,267 Mi (98.68% of node allocatable)** |
| CPU request headroom | **482m** |
| Memory request headroom | **310.35 Mi** |
| Active containers without explicit CPU request | 23 |
| Active containers without explicit memory request | 23 |
| PVC Bound / PVC total | 15 / 15 |
| PVC requested capacity | 52 GiB, NOT used bytes |

**Temporal correction:** the earlier collector output (07:55 UTC) showed 3 Pending pods and 30m/190Mi of additional Pending-container requests. This 08:10 capture shows **zero Pending**. The two captures are not contradictory; cluster state changed. Do not permanently classify the 3 historical Pending as permanently unschedulable.

## 2. Namespace-prefix partition (not a workload migration filter)

| Static classification of namespace names | Running pods | CPU requests | RAM requests | CPU share | RAM share |
|---|---:|---:|---:|---:|---:|
| Namespace name starts with `openshift-` | 108 | **4,603m** | **14,305 Mi** | **62.90%** | **61.48%** |
| All other namespace names | 41 | **2,715m** | **8,962 Mi** | **37.10%** | **38.52%** |
| **Total** | **149** | **7,318m** | **23,267 Mi** | **100%** | **100%** |

Non-OpenShift RAM = **8,962 Mi / 1024 ≈ 8.75 GiB**. OpenShift-prefix RAM = **14,305 Mi / 1024 ≈ 13.97 GiB**.

This is a **literal namespace string-prefix split only**. It is not an approved business-vs-infrastructure inventory:
- OpenShift namespaces can include Argo CD, Tekton, monitoring, operator/controller and networking components that may need replacement or ongoing worker resources on AKS/EKS/GKE.
- Other namespaces include Keycloak, shared OpenTelemetry, API gateway, IBM MQ and application databases. They are not purely stateless business applications.
- The managed Kubernetes control plane is provider-owned, but cluster operators/agents, workload monitoring, ingress, storage/network drivers and remaining shared capabilities require explicit target architecture and cost.
- The local hostpath provisioner may disappear or be replaced with billable dynamic storage; it is not a cloud managed database or backup service.
- Data Lakehouse Kind is separate and not included.
- Runnning requests are **scheduler declarations**, not actual P95/P99 utilization, required cloud worker capacity, production SLA or an IOPS metric.

## 3. Corrected preliminary conclusion

The earlier headline of 7.3 vCPU / 22.7 GiB requested by CRC **overstates the amount that can be attributed to non-`openshift-*` namespaces**. Conversely, it would be an error to deduct the **entire** 4.6 vCPU / 14.0 GiB OpenShift-prefix footprint and assume zero equivalent operations cost after moving to managed Kubernetes.

**Practical outcome:** 2.715 vCPU / 8.75 GiB in other namespaces is a **measured declarations baseline** to investigate, not an approved two-node AKS/EKS/GKE specification. The existing planned 2×4vCPU/16Gi node `targeted-demo` remains **SELECTIVE_WORKLOADS_ONLY**; simultaneous full CRC portfolio migration, HA and regional TCO are not proven.

## 4. Closure work for I1

1. Disaggregate the 41 other-namespace pods into *product workload*, *stateful data/messaging*, *shared identity/observability/API* and *CRC-local-only* groups; identify parked workloads. Include still-needed operators from the `openshift-*` group.
2. Render exact cloud overlays and operator requirements; account for allocatable, node/pod scheduling, PDB, network and storage.
3. Add Kind Data Lakehouse separately, choosing whether it runs at the same time as CRC-derived apps.
4. Measure P95/P99 utilization at meaningful load, data growth/IOPS, PVC actually used, events and pod restart/OOM metrics.
5. Reprice each regional Cloud BOM (system pool, databases, messaging, disk, networking, management, logging, support and GPU/MQ where relevant) and verify direct provider SKUs.
6. Preserve `ASSESSMENT_ONLY`: no cloud spend without explicit approval.

**Evidence gate:** `I1_CRC_NAMESPACE_SEGMENTATION_OBSERVED / I1_NOT_CLOSED`. Earlier 07:55 values are historical and superseded for the single-point pod inventory by the 08:10 capture.

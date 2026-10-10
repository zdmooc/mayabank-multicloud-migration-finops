# I1 — Where is Wero in CRC? Separate runtime scope clarification

**2026-10-10 · REPO/SNAPSHOT_REFERENCES_ONLY · NO LIVE CLI ACCESS**

The operator's OpenShift console screenshot explicitly selects the namespace `wero-poc` and shows Deployments (for example `payment-service`, `consumer-psp`, `api-gateway`, `mock-wero`), Service objects, a historical PVC and multiple `*-build` pods. This proves that Kubernetes objects exist in the console, **not** that their application pods are currently running or available. The console also has an **Error or Warning** status filter enabled.

## Canonical evidence

- `cadrage_202682030/portfolio/RUNTIME_DEPLOYMENT_MATRIX.md` dated 2026-10-07: `Wero historical | wero-poc | SCALE0 / REFERENCE ; runtime ARCHIVE/CLEANUP_CANDIDATE, physical cleanup deferred`.
- `cadrage_202682030/portfolio/LOCAL_CRC_RUNTIME_INVENTORY_2026-10-03.md`: `wero-organisme-poc` present historically at scale 0; Argo CD application `wero-poc-crc` was listed, without claiming current reconciliation.
- `zdmooc/wero-organisme-poc`: independently maintained reference repository. `gitops/base/runtime.yaml` has nonzero declared replicas (e.g., 2 for `api-gateway`), which can differ from the actual observed cluster scale. The current intended GitOps desired state versus live state **must be checked**, not inferred.
- `zdmooc/mayabank-instant-payments-resilience-platform`: a *separate* actively demonstrated Instant Payments platform under `instant-payments-local` with a distinct `wero-ui` component and payment consumer/acceptor APIs. Do not merge the two GitHub repositories simply because both reference Wero.

## Why not in the I1 CPU/RAM tables

`scripts/summarize-local-inventory.py` filters to `Running` and `Pending` pods when aggregating active resource requests, not to all Deployment/Service/PVC definitions. The 2026-10-10 08:10 UTC private CSV summary counted 149 Running, 0 Pending, and 121 historical Succeeded/Failed; **no running `wero-poc` workloads were evidenced in the supplied group output**. This is consistent with the dated `SCALE0` assessment but not direct proof of the current deployment replica count.

The `wero-poc` source repository remains a **Wero-specific reference/resilience workstream**, not automatically included in the baseline active CRC load or the first Instant Payments AKS pilot. Consider it for a later *separately bounded* migration scenario only after explicit scope choice and a fresh active runtime inventory. The pilot should not duplicate an entire second Wero stack by accident.

## Read-only checks for the operator (Git Bash)

```bash
oc -n wero-poc get deployments -o custom-columns='NAME:.metadata.name,DESIRED:.spec.replicas,READY:.status.readyReplicas,AVAILABLE:.status.availableReplicas'
oc -n wero-poc get pods
oc -n wero-poc get pvc
oc -n instant-payments-local get deployment wero-ui
oc -n openshift-gitops get applications.argoproj.io wero-poc-crc
```

If the last two objects differ by naming/version, list the corresponding namespace first; do not mutate the cluster or apply `scale` to resolve a discovery discrepancy.

**Safety:** CRC already showed about 98.7% requested memory against node allocatable. Reactivating `wero-poc` without a workload scale-down/budget plan can cause Pending, eviction or OOM. No destructive cleanup or scale-up is authorized by this assessment.

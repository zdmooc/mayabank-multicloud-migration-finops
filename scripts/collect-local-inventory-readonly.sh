#!/usr/bin/env bash
# I1 local read-only inventory for Git Bash/Linux. NO cloud or Kubernetes mutations.
# Usage: bash scripts/collect-local-inventory-readonly.sh [oc|kubectl] [output-dir]
set -euo pipefail
CLI="${1:-oc}"
DEST="${2:-evidence/local/private-$(date -u +%Y%m%dT%H%M%SZ)}"
case "$CLI" in oc|kubectl) ;; *) echo "CLI must be oc or kubectl" >&2; exit 2 ;; esac
command -v "$CLI" >/dev/null || { echo "$CLI not found" >&2; exit 2; }
command -v jq >/dev/null || { echo "jq required" >&2; exit 2; }
mkdir -p "$DEST"
echo "I1_COLLECTION_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee "$DEST/README.txt"
echo "COMMAND=$CLI; READ_ONLY=true" | tee -a "$DEST/README.txt"

# Keep only resource requests/limits and pod state; intentionally never serialize
# full Pod JSON, Secret, Env, ConfigMap, kubeconfig, token or private networking.
"$CLI" get pods -A -o json |
jq -r '(["namespace","pod","phase","container","cpu_request","memory_request","cpu_limit","memory_limit"] | @csv),
(.items[] | . as $pod | .spec.containers[]? |
  [ $pod.metadata.namespace, $pod.metadata.name,
    ($pod.status.phase // ""), .name,
    (.resources.requests.cpu // ""), (.resources.requests.memory // ""),
    (.resources.limits.cpu // ""), (.resources.limits.memory // "") ] | @csv)'  > "$DEST/pod-resources.csv"

"$CLI" get pvc -A -o json |
jq -r '(["namespace","pvc","phase","storage_class","requested_storage"] | @csv),
(.items[] |
  [.metadata.namespace,.metadata.name,(.status.phase // ""),
   (.spec.storageClassName // ""),(.spec.resources.requests.storage // "")] | @csv)'  > "$DEST/pvc-requests.csv"

"$CLI" get nodes -o json |
jq -r '(["node","allocatable_cpu","allocatable_memory","capacity_cpu","capacity_memory"] | @csv),
(.items[] |
  [.metadata.name,(.status.allocatable.cpu // ""),
   (.status.allocatable.memory // ""),(.status.capacity.cpu // ""),
   (.status.capacity.memory // "")] | @csv)' > "$DEST/node-allocatable.csv"

if "$CLI" top pods -A --containers >"$DEST/top-pods-now.txt" 2>"$DEST/top-pods-warning.txt"; then
  echo "POD_TOP=AVAILABLE_CURRENT_SAMPLE_ONLY" | tee -a "$DEST/README.txt"
else
  echo "POD_TOP=UNAVAILABLE_NOT_AN_ERROR" | tee -a "$DEST/README.txt"
fi
if "$CLI" top nodes > "$DEST/top-nodes-now.txt" 2>>"$DEST/top-pods-warning.txt"; then
 echo "NODE_TOP=AVAILABLE_CURRENT_SAMPLE_ONLY" | tee -a "$DEST/README.txt"
else
 echo "NODE_TOP=UNAVAILABLE_NOT_AN_ERROR" | tee -a "$DEST/README.txt"
fi

echo "I1_COLLECTION_FINISHED=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$DEST/README.txt"
echo "SANITIZE REVIEW REQUIRED: do not publish raw node names, namespaces, pod names or support errors."
echo "Outputs: $DEST; gitignore protects evidence/local/ but review before sharing."

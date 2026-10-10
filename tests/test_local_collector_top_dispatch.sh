#!/usr/bin/env bash
# Offline regression: never contacts real CRC or Kubernetes.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin"
cat >"$TMP/bin/oc" <<'MOCK'
#!/usr/bin/env bash
set -euo pipefail
CLI="$(basename "$0")"
if [ "${1:-}" = "get" ]; then
  case "${2:-}" in
    pods|pvc|nodes) printf '{"items":[]}\n'; exit 0 ;;
  esac
fi
if [ "$CLI" = "oc" ]; then
  [ "${1:-}" = "adm" ] && [ "${2:-}" = "top" ] || { echo "unexpected oc subcommand" >&2; exit 3; }
  shift 2
else
  [ "${1:-}" = "top" ] || { echo "unexpected kubectl subcommand" >&2; exit 3; }
  shift
fi
case "${1:-}" in
  pods)
    if [ "${OC_FAIL_CONTAINER_TOP:-0}" = "1" ] && printf ' %s ' "$@" | grep -q -- ' --containers '; then
      echo "fake unsupported --containers" >&2
      exit 5
    fi
    echo "NAMESPACE NAME CPU(cores) MEMORY(bytes)"
    echo "test synthetic-123 1m 8Mi"
    ;;
  nodes)
    echo "NAME CPU(cores) CPU(%) MEMORY(bytes) MEMORY(%)"
    echo "test-node 2m 1% 8Mi 2%"
    ;;
  *) echo "unexpected top target" >&2; exit 3 ;;
esac
MOCK
chmod +x "$TMP/bin/oc"
cp "$TMP/bin/oc" "$TMP/bin/kubectl"
export PATH="$TMP/bin:$PATH"

for CLI in oc kubectl; do
  bash "$ROOT/scripts/collect-local-inventory-readonly.sh" "$CLI" "$TMP/$CLI" > /dev/null
  grep -q 'POD_TOP=AVAILABLE_CONTAINER_LEVEL_CURRENT_SAMPLE_ONLY' "$TMP/$CLI/README.txt"
  grep -q 'NODE_TOP=AVAILABLE_CURRENT_SAMPLE_ONLY' "$TMP/$CLI/README.txt"
  grep -q 'synthetic-123' "$TMP/$CLI/top-pods-now.txt"
done

OC_FAIL_CONTAINER_TOP=1 bash "$ROOT/scripts/collect-local-inventory-readonly.sh" oc "$TMP/fallback" >/dev/null
grep -q 'POD_TOP=AVAILABLE_POD_LEVEL_CURRENT_SAMPLE_ONLY' "$TMP/fallback/README.txt"
grep -q 'synthetic-123' "$TMP/fallback/top-pods-now.txt"

echo "LOCAL_COLLECTOR_TOP_DISPATCH=PASS (oc adm top, kubectl top, fallback)"

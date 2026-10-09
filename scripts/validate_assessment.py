#!/usr/bin/env python3
"""Offline checks for MayaBank assessment; never contacts cloud or cluster APIs."""
import csv
import sys
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "targeted-demo": (2, 8, 32, 150, 160),
    "portfolio-integration": (6, 24, 96, 500, 730),
    "illustrative-ha": (10, 40, 160, 1500, 730),
}
ORIGINAL_PROVIDERS = {"Azure AKS", "AWS EKS", "GCP GKE"}
REGIONAL_PROVIDERS = {"Azure AKS Standard", "AWS EKS Standard", "GCP GKE Standard"}
CENT = Decimal("0.01")


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def rows(path):
    with (ROOT / path).open(newline="", encoding="utf-8") as f:
        data = list(csv.DictReader(f))
    assert data, f"{path}: empty"
    return data


def validate():
    inv = rows("inventory/repository-scope.csv")
    names = [r["repository"] for r in inv]
    assert len(names) == len(set(names))
    assert "mayabank-multicloud-migration-finops" in names
    assert "mayabank-instant-payments-resilience-platform" in names

    old = rows("finops/illustrative-budget-baseline.csv")
    assert len(old) == 9
    assert {r["provider"] for r in old} == ORIGINAL_PROVIDERS
    assert {r["scenario"] for r in old} == set(SCENARIOS)
    assert len({(r["scenario"], r["provider"]) for r in old}) == 9
    for r in old:
        n, vcpu, mem, gb, h = SCENARIOS[r["scenario"]]
        assert [int(r[z]) for z in ("planned_workers", "planned_vcpu", "planned_ram_gib", "persistent_storage_gib", "active_hours_month")] == [n, vcpu, mem, gb, h]
        assert r["price_status"] == "UNVERIFIED_ESTIMATE", "Never promote a historical placeholder"

    price_rows = rows("finops/region-sku-price-sources-2026-10-09.csv")
    assert len(price_rows) == 3
    sources = {r["provider"]: r for r in price_rows}
    assert set(sources) == REGIONAL_PROVIDERS
    for r in price_rows:
        assert r["compute_source_quality"] == "SECONDARY_PUBLIC_COMPARATOR"
        assert r["control_plane_source_quality"].startswith("OFFICIAL_")
        assert Decimal(r["control_plane_usd_hour"]) == Decimal("0.10")
        assert int(r["vcpu_per_node"]) == 4 and int(r["nominal_ram_gib"]) == 16
        assert r["compute_source"].startswith("https://")
        assert "2026-" in r["verification_date"]

    subtotals = rows("finops/compute-cluster-subtotal-2026-10-09.csv")
    assert len(subtotals) == 9
    assert len({(r["scenario"], r["provider"]) for r in subtotals}) == 9
    for r in subtotals:
        n, vcpu, mem, gb, h = SCENARIOS[r["scenario"]]
        p = sources[r["provider"]]
        assert r["region"] == p["region"] and r["sku"] == p["sku"]
        assert int(r["workers"]) == n
        assert int(r["workers_vcpu_total"]) == vcpu
        assert int(r["workers_nominal_ram_gib_total"]) == mem
        assert int(r["worker_hours_month"]) == h
        hourly = Decimal(p["worker_linux_usd_hour"])
        assert Decimal(r["vm_usd_hour"]) == hourly
        subtotal = hourly * n * h
        cluster = Decimal("0.10") * h
        assert money(r["vm_compute_usd_month"]) == money(subtotal)
        assert money(r["cluster_control_plane_usd_month"]) == money(cluster)
        assert money(r["compute_cluster_usd_month"]) == money(subtotal + cluster)
        assert "SECONDARY_COMPUTE" in r["accuracy"]
        assert "network_egress" in r["excluded"]

    components = rows("capacity-planning/declared-workload-requests-2026-10-09.csv")
    assert len(components) >= 18
    for r in components:
        replicas = int(r["replicas_assumed"])
        assert replicas >= 1
        assert int(r["request_cpu_m_per_replica"]) * replicas == int(r["total_cpu_m"])
        assert int(r["request_memory_mi_per_replica"]) * replicas == int(r["total_memory_mi"])
        assert r["evidence_class"] != "LIVE_MEASURED"
    assert sum(int(r["total_cpu_m"]) for r in components) == 3575
    assert sum(int(r["total_memory_mi"]) for r in components) == 10584

    scenario_text = (ROOT / "capacity-planning/scenarios.yaml").read_text(encoding="utf-8")
    for scenario in SCENARIOS:
        assert "id: " + scenario in scenario_text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "ASSESSMENT_ONLY" in readme and "I1_STATIC_EVIDENCE_PACK_READY" in readme
    assert (ROOT / ".gitignore").read_text(encoding="utf-8").find("evidence/local/") >= 0
    print("ASSESSMENT_CONTRACTS=PASS; regional_price_rows=3; compute_subtotals=9; manifest_request_rows=19; I1_STATIC_ONLY")


if __name__ == "__main__":
    try:
        validate()
    except (AssertionError, ValueError, KeyError, FileNotFoundError) as exc:
        print(f"ASSESSMENT_CONTRACTS=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

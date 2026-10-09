#!/usr/bin/env python3
"""Offline validation of MayaBank multicloud assessment contracts.

Requires Python standard library only. Never contacts cloud provider APIs.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = {
    "targeted-demo": (2, 8, 32, 150, 160),
    "portfolio-integration": (6, 24, 96, 500, 730),
    "illustrative-ha": (10, 40, 160, 1500, 730),
}
PROVIDERS = {"Azure AKS", "AWS EKS", "GCP GKE"}


def load_csv(path):
    with (ROOT / path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{path}: no rows")
    return rows


def validate():
    inv = load_csv("inventory/repository-scope.csv")
    names = [r["repository"] for r in inv]
    assert len(names) == len(set(names)), "Repository inventory contains duplicates"
    assert "mayabank-multicloud-migration-finops" in names
    assert "mayabank-instant-payments-resilience-platform" in names

    costs = load_csv("finops/illustrative-budget-baseline.csv")
    assert len(costs) == 9, "Expected exactly 3 x 3 planning rows"
    pair_counts = Counter((row["scenario"], row["provider"]) for row in costs)
    assert len(pair_counts) == 9 and all(v == 1 for v in pair_counts.values())
    assert {row["provider"] for row in costs} == PROVIDERS
    assert {row["scenario"] for row in costs} == set(SCENARIOS)
    for row in costs:
        n, vcpu, ram, storage, hours = SCENARIOS[row["scenario"]]
        for column, expected in [
            ("planned_workers", n), ("planned_vcpu", vcpu),
            ("planned_ram_gib", ram), ("persistent_storage_gib", storage),
            ("active_hours_month", hours),
        ]:
            assert int(row[column]) == expected, (row["scenario"], row["provider"], column)
        assert float(row["illustrative_total_usd_month"]) > 0
        assert row["price_status"] == "UNVERIFIED_ESTIMATE", "No simulated values may be promoted to a quote"
    text = (ROOT / "capacity-planning/scenarios.yaml").read_text(encoding="utf-8")
    for scenario in SCENARIOS:
        assert "id: " + scenario in text, scenario
    assert "ASSESSMENT_ONLY" in (ROOT / "README.md").read_text(encoding="utf-8")
    print("ASSESSMENT_CONTRACTS=PASS: 3 scenarios x 3 providers, inventory and caution labels")


if __name__ == "__main__":
    try:
        validate()
    except (AssertionError, ValueError, KeyError, FileNotFoundError) as exc:
        print(f"ASSESSMENT_CONTRACTS=FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

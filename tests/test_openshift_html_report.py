#!/usr/bin/env python3
"""Synthetic, offline HTML report tests. Never executes oc or accesses CRC."""
import importlib.util
from pathlib import Path
import unittest
import tempfile
import json

ROOT=Path(__file__).resolve().parents[1]
script=ROOT/"scripts"/"render_openshift_project_html.py"
spec=importlib.util.spec_from_file_location("crc_html_renderer",script)
html=importlib.util.module_from_spec(spec)
spec.loader.exec_module(html)

def sample(ns="wero-poc"):
    return {
      "namespace":ns,"generated_at_utc":"2026-10-10T12:00:00+00:00",
      "workloads":[
        {"kind":"Deployment","name":"payment-service","desired":0,"ready":0,"images":["registry:latest"],
         "pvc_claims":[],"emptydir_mounts":[],"cpu_req_m":0,"ram_req_mi":0,
         "top_cpu_m_if_covered":0,"top_ram_mi_if_covered":0},
        {"kind":"Deployment","name":"postgresql","desired":0,"ready":0,"images":["postgres:16"],
         "pvc_claims":["postgresql-data"],"emptydir_mounts":[],"cpu_req_m":0,"ram_req_mi":0,
         "top_cpu_m_if_covered":0,"top_ram_mi_if_covered":0}],
      "pod_history":{"historical_build_pods":27,"build_completed":24,
                     "build_failed":3,"build_other":0,"non_build_running_pods":0,
                     "build_groups":[{"buildconfig":"api-gateway","visible":5,"completed":4,"failed":1,
                                      "visible_build_numbers":[1,2,3,4,5]}]},
      "pvc":[{"name":"postgresql-data","phase":"Bound","requested":"1Gi",
              "reclaim":"Retain","actual_used_bytes":"NOT_MEASURED"}],
      "services":[{"name":"payment-service","type":"ClusterIP","workload_candidates":["payment-service"]},
                  {"name":"postgresql","type":"ClusterIP","workload_candidates":["postgresql"]}],
      "routes":[{"name":"api-gateway","service":"payment-service","tls":"none"}],
      "db_consumer_candidates":[],
      "gitops":[{"name":"wero-poc-crc","sync":"Unknown","health":"Healthy",
                 "automated":False,"conditions":["ComparisonError"]}],
      "counts":{"pods":27,"services":2,"routes":1,"pvc":1,
                "networkpolicies":2,"warning_events":0},
      "sample":{"top_container_match":"0/0","cpu_req_m_active_containers":0,
                "cpu_top_m_matched_only":None,"ram_req_mi_active_containers":0,
                "ram_top_mi_matched_only":None},
      "unavailable_or_forbidden_resources":[],"limitations":["No SQL measured"],
      "findings":[{"severity":"P1","code":"GITOPS_NOT_SYNCED",
                   "detail":"ComparisonError <script>alert('bad')</script>",
                   "evidence":"Status metadata"}]
    }

class HtmlReportTest(unittest.TestCase):
    def test_wero_all_sections_and_sanitization(self):
        output=html.render_html(sample())
        self.assertIn('<html lang="fr">',output)
        self.assertIn("Diagramme de séquence",output)
        self.assertIn("Architecture réseau",output)
        self.assertIn("Stockage et durabilité",output)
        self.assertIn("GITOPS_NOT_SYNCED",output)
        self.assertIn("NO_DELETE",output)
        self.assertIn("oc -n wero-poc get deployments",output)
        self.assertIn("64 Mio",output)
        self.assertIn("Historique de construction OpenShift",output)
        self.assertIn("Builds visibles",output)
        self.assertIn("Pods builds",output)
        self.assertIn("27",output)
        self.assertIn("24",output)
        self.assertIn("api-gateway",output)
        self.assertIn("api-gateway",output)
        self.assertNotIn("<script>alert('bad')</script>",output)
        self.assertIn("&lt;script&gt;",output)
        self.assertNotIn("https://cdn",output)

    def test_generic_does_not_claim_wero_architecture(self):
        output=html.render_html(sample("tradeops"))
        self.assertIn("tradeops",output)
        self.assertNotIn("Wero V2/V6",output)
        self.assertIn("Séquence pédagogique",output)

    def test_offline_existing_json(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/"evidence"/"local"/"private-openshift-audit-test"
            root.mkdir(parents=True)
            inp=root/"wero-poc.report.json"
            inp.write_text(json.dumps(sample()),encoding="utf-8")
            self.assertEqual(html.main([str(inp)]),0)
            result=root/"wero-poc.report.html"
            self.assertTrue(result.exists())
            self.assertIn("Architecture applicative",result.read_text(encoding="utf-8"))

if __name__=="__main__":
    unittest.main()

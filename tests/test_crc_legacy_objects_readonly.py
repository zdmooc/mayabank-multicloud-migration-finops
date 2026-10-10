"""Offline regression tests for non-Pod CRC legacy metadata audit."""
from __future__ import annotations
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import json
from types import SimpleNamespace
from unittest.mock import patch
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-crc-legacy-objects-readonly.py"
spec = importlib.util.spec_from_file_location("crc_legacy", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
NOW = datetime(2026, 10, 10, tzinfo=timezone.utc)

def obj(name, ns, **properties):
    return {"metadata": {
        "name": name, "namespace": ns,
        "creationTimestamp": "2026-09-09T09:00:00Z",
    }, **properties}

def sample():
    all_types = {kind: [] for kind in module.RESOURCE_TYPES}
    all_types["deployments"] = [obj("api", "active-app")]
    all_types["replicasets"] = [
        {**obj("api-old", "active-app", spec={"replicas": 0}, status={"replicas": 0}),
         "metadata": {**obj("api-old", "active-app")["metadata"],
                      "ownerReferences": [{"kind": "Deployment", "name": "api"}]}},
        obj("orphan", "some-poc", spec={"replicas": 0}, status={"replicas": 0}),
        obj("api-live", "active-app", spec={"replicas": 1}, status={"replicas": 1}),
    ]
    all_types["buildconfigs"] = [obj("api-build", "active-app")]
    build = obj("api-build-1", "active-app", status={"phase": "Complete"})
    build["metadata"]["labels"] = {"openshift.io/build-config.name": "api-build"}
    all_types["builds"] = [
        build,
        obj("bad-1", "some-poc", status={"phase": "Failed"}),
        obj("building-2", "some-poc", status={"phase": "Running"}),
    ]
    all_types["jobs"] = [obj("job-old", "some-poc", status={"succeeded": 1})]
    all_types["cronjobs"] = [obj("cron-paused", "some-poc", spec={"suspend": True})]
    all_types["pvc"] = [obj("db", "some-poc", status={"phase": "Bound"})]
    all_types["imagestreams"] = [
        obj("api", "some-poc", status={
            "tags": [{"tag": "latest", "items": [{"image": "sha256:a"}, {"image": "sha256:b"}]}]
        })
    ]
    all_types["routes"] = [obj("api", "active-app")]
    return all_types


class LegacyAuditContract(unittest.TestCase):
    def test_counts_and_rollback_not_authorized(self):
        result = module.analysis(sample(), NOW)
        self.assertEqual(result["totals"]["replicasets"], 3)
        self.assertEqual(result["zero_rs_total"], 2)
        self.assertEqual(result["zero_rs"]["active-app"]["owned_by_existing_deployment"], 1)
        self.assertEqual(result["zero_rs"]["some-poc"]["no_deployment_owner"], 1)
        self.assertEqual(result["zero_rs"]["active-app"]["zero_14d"], 1)
        self.assertEqual(result["terminal_build_total"], 2)
        self.assertEqual(result["terminal_builds"]["active-app"]["with_current_buildconfig"], 1)
        self.assertEqual(result["terminal_builds"]["some-poc"]["without_matched_buildconfig"], 1)
        self.assertEqual(result["terminal_builds"]["some-poc"]["nonterminal"], 1)
        self.assertEqual(result["totals"]["imagestream_status_tags"], 1)
        self.assertEqual(result["totals"]["imagestream_tag_events"], 2)
        self.assertEqual(result["totals"]["jobs_terminal"], 1)
        self.assertEqual(result["totals"]["cronjobs_suspended"], 1)
        self.assertEqual(result["totals"]["pvc_bound"], 1)


    def test_buildconfig_history_limits_and_missing_links(self):
        items = sample()
        items["buildconfigs"] = [
            obj("payments", "mayabank-mq-build",
                spec={"successfulBuildsHistoryLimit": 1, "failedBuildsHistoryLimit": 2})
        ]
        def build(name, phase, owner=None):
            b = obj(name, "mayabank-mq-build", status={"phase": phase})
            if owner is not None:
                b["metadata"]["labels"] = {"openshift.io/build-config.name": owner}
            return b
        items["builds"] = [
            build("payments-1", "Complete", "payments"),
            build("payments-2", "Complete", "payments"),
            build("payments-3", "Failed", "payments"),
            build("payments-4", "Cancelled", "payments"),
            build("payments-5", "Running", "payments"),
            build("lost", "Complete"),
            build("old-config-1", "Complete", "deleted-config"),
        ]
        rows = module.build_retention(items)
        self.assertEqual(len(rows["rows"]), 1)
        row = rows["rows"][0]
        self.assertEqual(row["successful_limit"], 1)
        self.assertEqual(row["failed_limit"], 2)
        self.assertEqual(row["complete"], 2)
        self.assertEqual(row["unsuccessful"], 2)
        self.assertEqual(row["nonterminal"], 1)
        self.assertEqual(row["complete_above_limit"], 1)
        self.assertEqual(row["unsuccessful_above_limit"], 0)
        self.assertEqual(rows["unmatched"]["missing_buildconfig_label"], 1)
        self.assertEqual(rows["unmatched"]["buildconfig_not_found"], 1)

    def test_new_revision_not_aged(self):
        self.assertEqual(module.age_days("2026-10-09T09:00:00Z", NOW), 0)
        self.assertIsNone(module.age_days(None, NOW))
        self.assertIsNone(module.age_days("not-a-timestamp", NOW))

    def test_oc_invocation_has_no_secret_or_mutation(self):
        fake = SimpleNamespace(returncode=0, stdout=json.dumps({"items": []}), stderr="")
        with patch.object(module.subprocess, "run", return_value=fake) as mocked:
            self.assertEqual(module.run_oc("replicasets"), [])
            argv = mocked.call_args.args[0]
            self.assertEqual(argv, ["oc", "get", "replicasets", "-A", "-o", "json"])
            self.assertNotIn("secret", " ".join(argv))
            self.assertFalse(any(x in argv for x in ["delete", "scale", "patch", "apply"]))

if __name__ == "__main__":
    unittest.main()

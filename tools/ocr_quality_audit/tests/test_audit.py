"""Synthetic test data only. No private Vexo screenshot or homologation report."""
import json
from decimal import Decimal
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit import ReportError, _number, analyze, compare, main, markdown  # noqa: E402


def sample(version="0.3.2"):
    return {
        "schema": "vexo-ocr-batch-report-v1", "appVersion": version,
        "testImages": 2, "summary": {
            "checked": 6, "correct": 4, "discrepant": 2, "processingErrors": 0,
            "accuracyPct": 66.7,
        }, "perField": {
            "offerPrice": {"checked": 2, "correct": 1},
            "distanceKm": {"checked": 2, "correct": 1},
            "platform": {"checked": 2, "correct": 2},
        },
    }


class AuditTests(unittest.TestCase):
    def test_aggregates_and_financial_caution(self):
        a = analyze(sample())
        self.assertEqual(a["totals"]["accuracyPct"], 66.67)
        self.assertEqual(a["perField"]["offerPrice"]["errors"], 1)
        self.assertEqual(a["reviewFlags"], [])
        self.assertIn("offerPrice", a["riskBearingFieldsWithErrors"])
        self.assertTrue(any("severity cannot be confirmed" in x for x in a["warnings"]))

    def test_mismatch_details_flag_only_supported_financial_fields(self):
        doc = sample()
        doc["discrepancies"] = [
            {"field": "offerPrice", "expected": "R$ 43,09", "observed": "R$ 4,09", "caseId": "synthetic-1"},
            {"field": "distanceKm", "expected": "5,0 km", "actual": "50 km", "caseId": "synthetic-2"},
        ]
        audit = analyze(doc)
        self.assertEqual(audit["reviewFlags"][0]["status"], "critical_review")
        self.assertEqual(audit["reviewFlags"][0]["absoluteDifference"], "39.00")
        self.assertEqual(audit["reviewFlags"][1]["status"], "distance_review")
        self.assertEqual(audit["reviewFlags"][1]["absoluteDifference"], "45.0")

    def test_missing_detail_values_not_converted_to_fact(self):
        doc = sample()
        doc["discrepancies"] = [{"field": "offerPrice"}, {"field": "distanceKm", "expected": 4, "actual": 4}]
        a = analyze(doc)
        self.assertEqual(len(a["reviewFlags"]), 1)
        self.assertEqual(a["reviewFlags"][0]["status"], "unquantified_missing_values")
        self.assertTrue(any("equivalent" in w for w in a["warnings"]))

    def test_untrusted_or_inconsistent_report_rejected_or_warned(self):
        doc = sample()
        doc["schema"] = "vexo-backup-v1"
        with self.assertRaises(ReportError):
            analyze(doc)
        doc = sample()
        doc["perField"]["platform"]["correct"] = 3
        with self.assertRaises(ReportError):
            analyze(doc)
        doc = sample()
        doc["summary"]["correct"] = 5
        self.assertTrue(any("reconcile" in x for x in analyze(doc)["warnings"]))

    def test_comparison_not_claimed_paired(self):
        before = analyze(sample("0.3.2"))
        after_doc = sample("0.3.3")
        after_doc["perField"]["distanceKm"]["correct"] = 2
        after_doc["summary"].update({"correct": 5, "discrepant": 1, "accuracyPct": 83.33})
        after = analyze(after_doc)
        diff = compare(before, after)
        self.assertEqual(diff["datasetStatus"], "unverified_dataset_identity")
        self.assertEqual(diff["perField"]["distanceKm"]["deltaPercentagePoints"], 50.0)
        self.assertIn("not confirmed identical", " ".join(diff["notes"]))
        self.assertIn("Comparison", markdown(after, diff))

    def test_dataset_markers_and_missing_fields(self):
        older = sample("0.3.2")
        older["datasetHash"] = "abc"
        latest = sample("0.3.3")
        latest["datasetHash"] = "xyz"
        self.assertEqual(compare(analyze(older), analyze(latest))["datasetStatus"], "different_dataset_markers")

    def test_currency_parser(self):
        self.assertEqual(_number("R$ 1.234,56"), Decimal("1234.56"))
        self.assertEqual(_number("R$ 12,50"), Decimal("12.5"))
        self.assertEqual(_number("1,5x"), Decimal("1.5"))
        self.assertIsNone(_number("valor não disponível"))

    def test_cli_writes_json(self):
        with tempfile.TemporaryDirectory() as directory:
            src = Path(directory, "sample.json")
            dst = Path(directory, "result.json")
            src.write_text(json.dumps(sample()), encoding="utf-8")
            self.assertEqual(main([str(src), "--format", "json", "--output", str(dst)]), 0)
            result = json.loads(dst.read_text(encoding="utf-8"))
            self.assertEqual(result["audit"]["totals"]["errors"], 2)


    def test_samples_structure_and_risk_reconciliation(self):
        """Synthetic report shaped like the Vexo 0.3.3 export."""
        doc = sample()
        doc["samples"] = [
            {"id": "synthetic-A", "tested": 3, "correct": 1,
             "financialSafety": {"basicFieldsUsable": False},
             "ocrEvidence": {"offerPrice": {"expectedNumberSeenInRawOCR": True}},
             "fields": {
                 "offerPrice": {"expected": 43.09, "actual": "4,09", "status": "wrong"},
                 "distanceKm": {"expected": 10, "actual": "1", "status": "wrong"},
                 "platform": {"expected": "99", "actual": "99", "status": "ok"}}},
            {"id": "synthetic-B", "tested": 3, "correct": 3,
             "financialSafety": {"basicFieldsUsable": True},
             "fields": {
                 "offerPrice": {"expected": 9, "actual": "9,00", "status": "ok"},
                 "distanceKm": {"expected": 10, "actual": "10", "status": "ok"},
                 "platform": {"expected": "99", "actual": "99", "status": "ok"}}},
        ]
        audit = analyze(doc)
        self.assertEqual(audit["sampleAudit"]["statusChecked"], 6)
        self.assertEqual(audit["sampleAudit"]["statusCorrect"], 4)
        self.assertEqual(audit["sampleAudit"]["financialReviewCount"], 1)
        self.assertEqual(audit["sampleAudit"]["distanceReviewCount"], 1)
        self.assertEqual(audit["sampleAudit"]["basicFieldsUnusableCases"], ["synthetic-A"])
        self.assertEqual(audit["reviewFlags"][0]["absoluteDifference"], "39.00")
        self.assertTrue(audit["reviewFlags"][0]["reportedExpectedNumberSeenInRawOCR"])
        self.assertIn("synthetic-A", markdown(audit))

    def test_missing_surge_is_not_assumed_zero(self):
        doc = {"schema": "vexo-ocr-batch-report-v1", "appVersion": "test-only",
               "testImages": 1, "summary": {"checked": 1, "correct": 0,
               "discrepant": 1, "processingErrors": 0, "accuracyPct": 0},
               "perField": {"surge": {"checked": 1, "correct": 0}},
               "samples": [{"id": "synthetic-C", "tested": 1, "correct": 0,
                            "financialSafety": {"basicFieldsUsable": True},
                            "ocrEvidence": {"surge": {"expectedNumberSeenInRawOCR": False}},
                            "fields": {"surge": {"expected": 2.8, "actual": "", "status": "missing"}}}]}
        audit = analyze(doc)
        flagged = audit["reviewFlags"][0]
        self.assertTrue(flagged["magnitudeUnquantified"])
        self.assertNotIn("absoluteDifference", flagged)
        self.assertEqual(flagged["status"], "critical_review")
        self.assertEqual(audit["sampleAudit"]["basicFieldsUsableWithRiskIssues"], ["synthetic-C"])

    def test_samples_count_mismatch_warns(self):
        doc = sample()
        doc["samples"] = [{"id": "synthetic-incomplete", "tested": 1, "correct": 1,
                           "fields": {"platform": {"expected": "99", "actual": "99", "status": "ok"}}}]
        audit = analyze(doc)
        self.assertTrue(any("samples count differs" in w for w in audit["warnings"]))
        self.assertTrue(any("sample status totals differ" in w for w in audit["warnings"]))
        self.assertTrue(any("sample field totals disagree" in w for w in audit["warnings"]))



    def test_ten_sample_033_shape_reconciles_all_five_risks(self):
        """Synthetic placeholders, using only the supplied 0.3.3 field-presence/status layout."""
        base = ["platform", "offerType", "offerPrice", "pickupMin", "pickupKm",
                "tripMin", "tripKm", "rating", "rides", "negotiations"]
        extra = {
            1: ["payment"], 2: [], 3: ["surge"], 4: ["surge"], 5: [],
            6: ["payment", "perKm"], 7: ["payment", "perKm", "surge"],
            8: ["perKm", "surge"], 9: [], 10: ["perKm"],
        }
        errors = {(3, "tripKm"): (11.8, "1,8", "wrong"),
                  (3, "surge"): (2.8, "", "missing"),
                  (7, "surge"): (1.1, "", "missing"),
                  (8, "surge"): (2.2, "", "missing"),
                  (10, "perKm"): (1.28, "", "missing")}
        counts = {}
        samples = []
        for number in range(1, 11):
            details = {}
            for field in base + extra[number]:
                exp, act, status = errors.get((number, field), (1, "1", "ok"))
                details[field] = {"expected": exp, "actual": act, "status": status}
                row = counts.setdefault(field, [0, 0])
                row[0] += 1
                row[1] += (status == "ok")
            samples.append({"id": f"synthetic-{number}", "fields": details,
                            "tested": len(details),
                            "correct": sum(x["status"] == "ok" for x in details.values()),
                            "financialSafety": {"basicFieldsUsable": number != 3}})
        doc = {"schema": "vexo-ocr-batch-report-v1", "appVersion": "0.3.3-synthetic",
               "testImages": 10, "summary": {"checked": 111, "correct": 106,
               "discrepant": 5, "processingErrors": 0, "accuracyPct": 95.5},
               "perField": {k: {"checked": n, "correct": good}
                            for k, (n, good) in counts.items()}, "samples": samples}
        result = analyze(doc)
        self.assertEqual((result["sampleAudit"]["statusChecked"], result["sampleAudit"]["statusCorrect"]), (111, 106))
        self.assertEqual(len(result["reviewFlags"]), 5)
        self.assertEqual(result["sampleAudit"]["financialReviewCount"], 4)
        self.assertEqual(result["sampleAudit"]["distanceReviewCount"], 1)
        self.assertEqual(result["perField"]["surge"]["accuracyPct"], 25.0)
        self.assertEqual(result["perField"]["perKm"]["accuracyPct"], 75.0)
        self.assertEqual(result["perField"]["tripKm"]["accuracyPct"], 90.0)
        self.assertFalse(any("totals disagree" in w or "totals differ" in w for w in result["warnings"]))



if __name__ == "__main__":
    unittest.main()

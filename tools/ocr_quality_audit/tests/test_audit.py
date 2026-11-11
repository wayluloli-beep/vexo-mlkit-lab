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


if __name__ == "__main__":
    unittest.main()

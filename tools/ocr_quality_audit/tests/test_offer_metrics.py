"""Synthetic samples for per-offer risk rates; no real 99 driver data."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit import analyze, markdown


class OfferMetricsTests(unittest.TestCase):
    def test_multiple_field_errors_count_once_per_offer(self):
        samples = []
        for idx in range(4):
            items = {
                "offerPrice": {"expected": 10, "actual": "10", "status": "ok"},
                "tripKm": {"expected": 5, "actual": "5", "status": "ok"},
                "rides": {"expected": 40, "actual": "40", "status": "ok"},
            }
            if idx == 0:
                items["offerPrice"] = {"expected": 10, "actual": "1", "status": "wrong"}
                items["tripKm"] = {"expected": 5, "actual": "1", "status": "wrong"}
            elif idx == 1:
                items["offerPrice"] = {"expected": 10, "actual": "", "status": "missing"}
            elif idx == 2:
                items["rides"] = {"expected": None, "actual": "40", "status": "false_positive"}
            samples.append({"id": f"synthetic-{idx}", "fields": items, "tested": 3,
                            "correct": sum(x["status"] == "ok" for x in items.values())})
        result = analyze({
            "schema": "vexo-ocr-batch-report-v1", "appVersion": "synthetic-only",
            "testImages": 4, "summary": {"checked": 12, "correct": 8, "discrepant": 4,
                                           "processingErrors": 0, "accuracyPct": 66.67},
            "perField": {"offerPrice": {"checked": 4, "correct": 2},
                         "tripKm": {"checked": 4, "correct": 3},
                         "rides": {"checked": 4, "correct": 3}},
            "samples": samples,
        })
        risk = result["sampleAudit"]["offerRisk"]
        self.assertEqual(risk["evaluatedOffers"], 4)
        self.assertEqual(risk["offersWithAnyError"], 3)
        self.assertEqual(risk["offersWithDirectFinancialError"], 2)
        self.assertEqual(risk["offersWithDistanceError"], 1)
        self.assertEqual(risk["offersWithDecisionRelevantError"], 2)
        self.assertEqual(risk["offersWithFalsePositive"], 1)
        self.assertEqual(risk["anyErrorRatePct"], 75.0)
        self.assertEqual(risk["decisionRelevantErrorRatePct"], 50.0)
        self.assertIn("Offers with financial/distance error: 2/4 (50.0%)", markdown(result))
        self.assertFalse(any("totals disagree" in w or "totals differ" in w for w in result["warnings"]))

    def test_zero_recognized_fields_not_treated_as_correct_offer(self):
        result = analyze({
            "schema": "vexo-ocr-batch-report-v1", "appVersion": "synthetic-empty",
            "testImages": 1, "summary": {"checked": 0, "correct": 0, "discrepant": 0,
                                          "processingErrors": 0, "accuracyPct": None},
            "perField": {"platform": {"checked": 0, "correct": 0}},
            "samples": [{"id": "no-fields", "tested": 0, "correct": 0, "fields": {}}],
        })
        risk = result["sampleAudit"]["offerRisk"]
        self.assertEqual(risk["evaluatedOffers"], 0)
        self.assertIsNone(risk["anyErrorRatePct"])
        self.assertTrue(any("excluded from per-offer denominator" in w for w in result["warnings"]))

    def test_aggregate_only_report_does_not_invent_offer_rate(self):
        result = analyze({
            "schema": "vexo-ocr-batch-report-v1", "appVersion": "summary-only",
            "testImages": 10, "summary": {"checked": 10, "correct": 9, "discrepant": 1,
                                           "processingErrors": 0, "accuracyPct": 90},
            "perField": {"offerPrice": {"checked": 10, "correct": 9}},
        })
        self.assertIsNone(result["sampleAudit"])
        self.assertNotIn("Offers with any reported error:", markdown(result))


if __name__ == "__main__":
    unittest.main()

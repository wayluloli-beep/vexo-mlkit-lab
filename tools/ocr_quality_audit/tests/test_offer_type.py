"""Detect a permissive offer-type evaluator inflating the 'correct' field count."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from audit import analyze


def sample_report(expected, actual):
    return {
        "schema": "vexo-ocr-batch-report-v1", "appVersion": "synthetic",
        "testImages": 1,
        "summary": {"checked": 1, "correct": 1, "discrepant": 0, "processingErrors": 0,
                    "accuracyPct": 100},
        "perField": {"offerType": {"checked": 1, "correct": 1}},
        "samples": [{"id": "fictional-image", "tested": 1, "correct": 1,
                     "fields": {"offerType": {"expected": expected, "actual": actual,
                                             "status": "ok"}}}],
    }


class OfferTypeAccuracyTests(unittest.TestCase):
    def test_entrega_moto_is_not_a_strict_match_for_moto(self):
        result = analyze(sample_report("Entrega Moto", "Moto"))
        self.assertTrue(any("type labels differ" in w for w in result["warnings"]))
        # Auditor cannot silently rewrite the Android generator's ground truth/count.
        self.assertEqual(result["totals"]["correct"], 1)

    def test_matching_type_has_no_false_warning(self):
        result = analyze(sample_report("Entrega Moto", "Entrega Moto"))
        self.assertFalse(any("type labels differ" in w for w in result["warnings"]))


if __name__ == "__main__":
    unittest.main()

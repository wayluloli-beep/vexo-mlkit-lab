"""All fixtures are fake counters; no real screen or OCR text is used."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_diagnostic_audit import analyze, DiagnosticInputError


def example(**overrides):
    data = {
        "schema": "vexo-live-capture-diagnostic-v1",
        "app": "Vexo Captura 0.4 experimental", "status": "CAPTURE_STOPPED",
        "diagnosticStage": "OCR_OK_NO_CONFIRMED_OFFER",
        "diagnosticExplanation": "placeholder text that must never be echoed",
        "framesReceived": 19, "ocrAttempts": 2, "ocrCompleted": 2,
        "ocrFailures": 0, "offersAlerted": 0, "offerContextCandidates": 0,
        "screenContextUncertain": 2, "screenContextRejected": 0,
        "financiallyUnconfirmedFrames": 0, "awaitingTwoStableReadings": 0,
        "capturedWindowVisibility": "visível", "noFieldAccuracyMeasured": True,
        "containsScreenshotOrOcrText": False, "privacyNote": "private placeholder",
    }
    data.update(overrides)
    return data


class LiveDiagnosticTests(unittest.TestCase):
    def test_19_frames_two_ocr_and_zero_alerts_not_guessed_as_financial(self):
        result = analyze(example())
        self.assertTrue(result["consistentCounters"])
        self.assertEqual(result["bottleneckHypothesis"], "NO_CLASSIFIED_OFFER_EVIDENCE")
        self.assertNotIn("private placeholder", str(result))

    def test_financial_guard_all_candidates_blocked(self):
        result = analyze(example(offerContextCandidates=2, screenContextUncertain=0,
                                 financiallyUnconfirmedFrames=2))
        self.assertEqual(result["bottleneckHypothesis"], "FINANCIAL_GUARD_REJECTED_ALL_CANDIDATES")

    def test_stability_unconfirmed(self):
        result = analyze(example(offerContextCandidates=2, screenContextUncertain=0,
                                 awaitingTwoStableReadings=2))
        self.assertEqual(result["bottleneckHypothesis"], "STABILITY_NOT_CONFIRMED_OR_EPISODE_UNCLEAR")

    def test_unknown_counter_cannot_be_exfiltrated(self):
        doc = example(rawOcr="fictional address 42")
        with self.assertRaises(DiagnosticInputError):
            analyze(doc)

    def test_inconsistent_outcome_counts(self):
        result = analyze(example(ocrAttempts=2, ocrCompleted=2, ocrFailures=1))
        self.assertIn("OCR_OUTCOMES_EXCEED_ATTEMPTS", result["violations"])

    def test_untrustworthy_schema_accuracy_claim_rejected(self):
        with self.assertRaises(DiagnosticInputError):
            analyze(example(noFieldAccuracyMeasured=False))
        with self.assertRaises(DiagnosticInputError):
            analyze(example(containsScreenshotOrOcrText=True))

    def test_report_stage_mismatch_is_detected(self):
        result = analyze(example(diagnosticStage="OFFER_ALERT_GENERATED"))
        self.assertIn("DECLARED_STAGE_MISMATCH", result["violations"])

    def test_context_exceeds_ocr(self):
        result = analyze(example(screenContextUncertain=3))
        self.assertIn("CONTEXT_COUNTS_EXCEED_COMPLETED_OCR", result["violations"])

    def test_boolean_disguised_as_number_is_rejected(self):
        with self.assertRaises(DiagnosticInputError):
            analyze(example(ocrCompleted=True))

    def test_no_frames_uses_state(self):
        counters = {"framesReceived": 0, "ocrAttempts": 0, "ocrCompleted": 0,
                    "screenContextUncertain": 0}
        d = example(**counters, diagnosticStage="NO_FRAMES_RECORDED")
        self.assertEqual(analyze(d)["bottleneckHypothesis"], "NO_FRAMES")

    def test_offers_alerted_not_accuracy(self):
        d = example(offerContextCandidates=1, screenContextUncertain=1,
                    offersAlerted=1, diagnosticStage="OFFER_ALERT_GENERATED")
        r = analyze(d)
        self.assertEqual(r["bottleneckHypothesis"], "ALERT_RECORDED_NOT_OCR_ACCURACY")
        self.assertIn("Counters cannot", r["limits"])


if __name__ == "__main__":
    unittest.main()

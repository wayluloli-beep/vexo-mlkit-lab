"""Vexo v3 telemetry regressions, only fabricated aggregate counters."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_diagnostic_audit import analyze, DiagnosticInputError
from compare_live_diagnostics import compare
from test_capture_diagnostic_v2 import v2


def v3(**overrides):
    data = v2(framesReceived=250, ocrAttempts=14, ocrCompleted=14,
              screenContextUncertain=11, offerContextCandidates=3,
              awaitingTwoStableReadings=2)
    data["schema"] = "vexo-live-capture-diagnostic-v3"
    data["discardedStaleOcrFrames"] = 2
    data["offerGateHeldFrames"] = 1
    data["candidatesWithout99Logo"] = 2
    data["contextEvidenceCounts"]["ocrReadsExamined"] = 12
    data.update(overrides)
    return data


class V3TelemetryTests(unittest.TestCase):
    def test_full_v3_is_accepted(self):
        r = analyze(v3())
        self.assertTrue(r["consistentCounters"], r["violations"])
        self.assertEqual(r["v3Counters"]["discardedStaleOcrFrames"], 2)

    def test_v3_rejects_missing_or_extra_keys(self):
        for name in ("discardedStaleOcrFrames", "offerGateHeldFrames", "candidatesWithout99Logo"):
            with self.subTest(name=name):
                d = v3()
                del d[name]
                with self.assertRaises(DiagnosticInputError):
                    analyze(d)
        with self.assertRaises(DiagnosticInputError):
            analyze(v3(rawOcrText="PRIVATE_FAKE"))

    def test_v3_rejects_boolean_or_text_or_negative_counts(self):
        for val in (True, "2", 2.3, None, -1):
            with self.subTest(val=val):
                with self.assertRaises(DiagnosticInputError):
                    analyze(v3(discardedStaleOcrFrames=val))

    def test_stale_must_be_subset_of_completed_ocr(self):
        d = v3(discardedStaleOcrFrames=15)
        self.assertIn("STALE_FRAMES_EXCEED_COMPLETED_OCR", analyze(d)["violations"])

    def test_context_evidence_cannot_count_stale_ocr(self):
        d = v3()
        d["contextEvidenceCounts"]["ocrReadsExamined"] = 13
        self.assertIn("EVIDENCE_READS_EXCEED_FRESH_OCR", analyze(d)["violations"])

    def test_held_gate_count_not_larger_than_candidates(self):
        d = v3(offerGateHeldFrames=4)
        self.assertIn("HELD_FRAMES_EXCEED_CANDIDATES", analyze(d)["violations"])

    def test_without_logo_not_larger_than_candidates(self):
        d = v3(candidatesWithout99Logo=4)
        self.assertIn("CANDIDATES_WITHOUT_LOGO_EXCEED_CANDIDATES", analyze(d)["violations"])

    def test_all_stale_ocr_can_have_zero_context_counts(self):
        d = v3(ocrAttempts=2, ocrCompleted=2,
               discardedStaleOcrFrames=2, offerContextCandidates=0,
               screenContextUncertain=0, financiallyUnconfirmedFrames=0,
               awaitingTwoStableReadings=0, offerGateHeldFrames=0,
               candidatesWithout99Logo=0, diagnosticStage="OCR_OK_NO_CONFIRMED_OFFER")
        d["contextEvidenceCounts"] = {k: 0 for k in d["contextEvidenceCounts"]}
        d.update(ocrLatencySamples=2, ocrLatencyLastMs=12359, ocrLatencyMeanMs=9022,
                 ocrLatencyP50Ms=5685, ocrLatencyP95Ms=12359, ocrLatencyMaxMs=12359)
        r = analyze(d)
        self.assertTrue(r["consistentCounters"], r["violations"])
        self.assertEqual(r["counters"]["ocrCompleted"], 2)
        self.assertEqual(r["v3Counters"]["discardedStaleOcrFrames"], 2)
        self.assertEqual(r["contextEvidenceCounts"]["ocrReadsExamined"], 0)
        self.assertEqual(r["bottleneckHypothesis"], "NO_CLASSIFIED_OFFER_EVIDENCE")

    def test_stopped_v3_valid(self):
        r = analyze(v3(status="CAPTURE_STOPPED"))
        self.assertTrue(r["consistentCounters"])

    def test_comparison_of_v2_and_v3_rejected(self):
        a = v3()
        b = dict(a)
        b["schema"] = "vexo-live-capture-diagnostic-v2"
        for k in ("discardedStaleOcrFrames", "offerGateHeldFrames", "candidatesWithout99Logo"):
            b.pop(k)
        self.assertEqual(compare(a, b)["reason"], "INCOMPATIBLE_DIAGNOSTIC_VERSIONS")

    def test_v3_deltas_are_conditional_on_session_identity(self):
        a = v3()
        b = v3(framesReceived=320, ocrAttempts=17, ocrCompleted=17,
               screenContextUncertain=13, offerContextCandidates=4,
               awaitingTwoStableReadings=3, discardedStaleOcrFrames=3,
               offerGateHeldFrames=2, candidatesWithout99Logo=3)
        b["contextEvidenceCounts"] = dict(a["contextEvidenceCounts"],
                                           ocrReadsExamined=14,
                                           readsWithActionButton=2,
                                           readsWithTwoDistances=2,
                                           readsWithTwoTimes=2,
                                           readsWithOfferModality=3,
                                           readsWith99Marker=3,
                                           readsWithPriceMarker=3,
                                           readsWithPartialOfferEvidence=3)
        b.update(ocrLatencySamples=10, ocrLatencyLastMs=260,
                 ocrLatencyP50Ms=350, ocrLatencyP95Ms=850,
                 ocrLatencyMaxMs=850)
        result = compare(a, b)
        self.assertTrue(result["canCompare"])
        self.assertFalse(result["sessionContinuityProven"])
        self.assertEqual(result["v3CounterDeltasIfSameSession"]["discardedStaleOcrFrames"], 1)
        self.assertEqual(result["v3CounterDeltasIfSameSession"]["offerGateHeldFrames"], 1)

    def test_v3_decreasing_stale_counter_detects_reset(self):
        a = v3()
        b = v3(discardedStaleOcrFrames=1)
        r = compare(a, b)
        self.assertFalse(r["canCompare"])
        self.assertIn("discardedStaleOcrFrames", r["decreasedCounters"])


if __name__ == "__main__":
    unittest.main()

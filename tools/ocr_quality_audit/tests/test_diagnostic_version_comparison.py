"""Synthetic v0.4 reports only; no real user diagnostics, OCR, or identifiers."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from live_diagnostic_audit import analyze, DiagnosticInputError
from compare_live_diagnostics import compare


def report(**kwargs):
    d = {
        "schema": "vexo-live-capture-diagnostic-v1",
        "app": "Vexo Captura 0.4 experimental",
        "status": "CAPTURE_ACTIVE",
        "diagnosticStage": "OFFER_ALERT_GENERATED",
        "diagnosticExplanation": "fictitious explanation should not appear in output",
        "framesReceived": 20, "ocrAttempts": 4, "ocrCompleted": 4,
        "ocrFailures": 0, "offersAlerted": 1, "offerContextCandidates": 2,
        "screenContextUncertain": 2, "screenContextRejected": 0,
        "financiallyUnconfirmedFrames": 0, "awaitingTwoStableReadings": 1,
        "capturedWindowVisibility": "visível",
        "noFieldAccuracyMeasured": True,
        "containsScreenshotOrOcrText": False,
        "privacyNote": "not returned",
    }
    d.update(kwargs)
    return d


def with_latency(d, **kwargs):
    n = {
        "ocrLatencySamples": 4, "ocrLatencyLastMs": 400,
        "ocrLatencyMeanMs": 550, "ocrLatencyP50Ms": 400,
        "ocrLatencyP95Ms": 1000, "ocrLatencyMaxMs": 1000,
    }
    n.update(kwargs)
    return dict(d, **n)


class DiagnosticVersionAndComparisonTests(unittest.TestCase):
    def test_old_v1_diagnostic_still_accepted(self):
        self.assertTrue(analyze(report())["consistentCounters"])
        self.assertIsNone(analyze(report())["latency"])

    def test_new_six_latency_fields_accepted(self):
        result = analyze(with_latency(report()))
        self.assertTrue(result["consistentCounters"])
        self.assertEqual(result["latency"]["ocrLatencySamples"], 4)

    def test_incomplete_latency_fields_rejected(self):
        d = with_latency(report())
        d.pop("ocrLatencyP95Ms")
        with self.assertRaises(DiagnosticInputError):
            analyze(d)

    def test_privacy_blocks_unlisted_field_even_with_latency(self):
        with self.assertRaises(DiagnosticInputError):
            analyze(with_latency(report(), rawOCR="fake private content"))

    def test_small_sample_p95_must_equal_max(self):
        d = with_latency(report(), ocrLatencyP95Ms=800)
        result = analyze(d)
        self.assertIn("SMALL_SAMPLE_P95_MUST_EQUAL_MAX", result["violations"])

    def test_quantile_order_and_sample_count(self):
        d = with_latency(report(), ocrLatencyP50Ms=1100)
        self.assertIn("LATENCY_QUANTILE_ORDER_VIOLATION", analyze(d)["violations"])
        d = with_latency(report(), ocrLatencySamples=5)
        self.assertIn("LATENCY_SAMPLES_EXCEED_OCR_ATTEMPTS", analyze(d)["violations"])

    def test_zero_samples_requires_zero_times(self):
        d = with_latency(report(), ocrLatencySamples=0)
        self.assertIn("LATENCY_WITHOUT_SAMPLES", analyze(d)["violations"])

    def test_list_enum_rejected_safely(self):
        with self.assertRaises(DiagnosticInputError):
            analyze(report(status=["CAPTURE_ACTIVE"]))

    def test_compare_two_monotonic_aggregate_snapshots(self):
        a = with_latency(report())
        b = with_latency(report(framesReceived=32, ocrAttempts=6, ocrCompleted=6,
                                 offerContextCandidates=4, screenContextUncertain=2),
                         ocrLatencySamples=6, ocrLatencyLastMs=300,
                         ocrLatencyMeanMs=450, ocrLatencyP50Ms=400,
                         ocrLatencyP95Ms=1000, ocrLatencyMaxMs=1000)
        compared = compare(a, b)
        self.assertTrue(compared["canCompare"])
        self.assertFalse(compared["sessionContinuityProven"])
        self.assertEqual(compared["counterDeltasIfSameSession"]["ocrCompleted"], 2)
        self.assertEqual(compared["counterDeltasIfSameSession"]["offersAlerted"], 0)
        self.assertEqual(compared["latencySampleDeltaIfSameSession"], 2)
        self.assertEqual(compared["crossSnapshotAnomalies"], [])
        self.assertNotIn("fictitious explanation", str(compared))

    def test_counter_reset_is_not_presented_as_progress(self):
        a = report()
        b = report(framesReceived=3, ocrAttempts=1, ocrCompleted=1,
                   offerContextCandidates=1, screenContextUncertain=0)
        result = compare(a, b)
        self.assertFalse(result["canCompare"])
        self.assertIn("framesReceived", result["decreasedCounters"])

    def test_cross_snapshot_p95_cannot_lose_previous_max_in_small_sample_window(self):
        a = with_latency(report())
        b = with_latency(report(framesReceived=32, ocrAttempts=6, ocrCompleted=6,
                                 offerContextCandidates=4, screenContextUncertain=2),
                         ocrLatencySamples=6, ocrLatencyLastMs=300,
                         ocrLatencyMeanMs=350, ocrLatencyP50Ms=250,
                         ocrLatencyP95Ms=600, ocrLatencyMaxMs=600)
        self.assertIn("P95_DROPPED_BELOW_PREVIOUS_MAX_WITH_SMALL_SAMPLE_WINDOW",
                      compare(a, b)["crossSnapshotAnomalies"])

    def test_cross_snapshot_counter_inconsistency_detected(self):
        a = report()
        b = report(framesReceived=24, ocrAttempts=4, ocrCompleted=4,
                   offerContextCandidates=3, screenContextUncertain=1,
                   offersAlerted=2)
        self.assertIn("NEW_ALERTS_EXCEED_NEW_CONTEXT_CANDIDATES",
                      compare(a, b)["crossSnapshotAnomalies"])

    def test_mixed_diagnostic_versions_not_comparable(self):
        result = compare(report(), with_latency(report()))
        self.assertFalse(result["canCompare"])
        self.assertEqual(result["reason"], "INCOMPATIBLE_DIAGNOSTIC_VERSIONS")

    def test_invalid_input_report_not_silently_compared(self):
        invalid = with_latency(report(), ocrLatencySamples=0)
        self.assertFalse(compare(invalid, with_latency(report()))["canCompare"])


if __name__ == "__main__":
    unittest.main()

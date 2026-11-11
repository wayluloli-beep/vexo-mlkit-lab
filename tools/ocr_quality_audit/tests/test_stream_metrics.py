"""All scenarios use invented metadata, never passenger or driver information."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stream_metrics import summarize, percentile95, profile_roi_budget
from stream_audit import Event as E, audit_stream

class MetricsTests(unittest.TestCase):
    def test_thirty_frames_one_offer(self):
        events = [E("start", 1)]
        for i in range(30):
            events.extend([E("frame", 1, i, group="fixtureA"), E("callback", 1, i, "OFFER_CANDIDATE", "fixtureA", notified=i == 0, inference_ms=100 + i)])
        events.append(E("stop", 1))
        self.assertEqual(audit_stream(events)["counts"]["unique_labeled_offers"], 1)
        self.assertEqual(summarize(events)["ocr_latency_p95_ms"], 128)
        self.assertEqual(summarize(events)["first_detection_lag_frames_p95"], 0)

    def test_equal_prices_not_used_for_identity(self):
        events = [E("frame", 1, 0, group="A"), E("callback", 1, 0, "OFFER_CANDIDATE", "A"), E("frame", 1, 1, group="B"), E("callback", 1, 1, "OFFER_CANDIDATE", "B")]
        self.assertEqual(summarize(events)["unique_detected_fixture_offers"], 2)

    def test_map_uncertain_and_stop(self):
        events = [E("start", 1), E("frame", 1, 0), E("callback", 1, 0, "NON_OFFER", notified=True), E("frame", 1, 1), E("callback", 1, 1, "UNCERTAIN", notified=True), E("stop", 1), E("callback", 1, 1, "OFFER_CANDIDATE", "A", ui_applied=True)]
        violations = [name for _, name in audit_stream(events)["violations"]]
        self.assertIn("notification_on_non_offer", violations)
        self.assertIn("notification_on_uncertain", violations)
        self.assertIn("callback_after_stop_applied", violations)

    def test_roi_shared_crop_reduces_duplicate_processing(self):
        self.assertEqual(profile_roi_budget(), {"old_calls": 4, "shared_calls": 2, "saved_calls": 2})
        self.assertEqual(profile_roi_budget(False, True)["saved_calls"], 0)
        self.assertEqual(profile_roi_budget(False, False)["old_calls"], 0)

    def test_p95_and_empty(self):
        self.assertIsNone(percentile95([]))
        self.assertEqual(percentile95([10,20,30,40,50,60,70,80,90,100]), 100)
        with self.assertRaises(ValueError): percentile95([-1])

    def test_first_detection_lag_is_frames_not_time(self):
        events = [E("frame", 1, 1, group="A"), E("frame", 1, 2, group="A"), E("callback", 1, 2, "OFFER_CANDIDATE", "A", inference_ms=175, roi_passes=2)]
        result = summarize(events)
        self.assertEqual(result["first_detection_lag_frames_p95"], 1)
        self.assertEqual(result["ocr_latency_p95_ms"], 175)
        self.assertEqual(result["roi_passes_total"], 2)

if __name__ == "__main__":
    unittest.main()

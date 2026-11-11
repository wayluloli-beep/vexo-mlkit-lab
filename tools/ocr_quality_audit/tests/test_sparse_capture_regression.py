"""Synthetic regression for sparse OCR: frame throughput is not OCR latency."""
import unittest
from tools.ocr_quality_audit.stream_audit import Event, audit_stream


class SparseCaptureRegression(unittest.TestCase):
    def test_24_frames_one_completed_ocr_no_offer(self):
        events = [Event("start", 41, at_ms=0)]
        events += [Event("frame", 41, seq=i, at_ms=i * 1000) for i in range(1, 25)]
        events += [
            Event("inference_start", 41, seq=1, at_ms=25000),
            Event("inference_end", 41, seq=1, at_ms=25120),
            Event("callback", 41, seq=1, context="UNCERTAIN",
                  guard_blocked=True, inference_ms=120, at_ms=25120),
            Event("stop", 41, at_ms=30000),
        ]
        result = audit_stream(events)
        self.assertEqual([], result["violations"])
        counts = result["counts"]
        self.assertEqual(24, counts["frames"])
        self.assertEqual(1, counts["inference_starts"])
        self.assertEqual(1, counts["inference_ends"])
        self.assertEqual(0, counts["notifications"])
        self.assertEqual(120, counts["inference_ms_total"])
        self.assertEqual(1, counts["guard_abstentions"])
        # 30 seconds of observation cannot be substituted for OCR duration.
        self.assertNotEqual(30000, counts["inference_ms_total"])

    def test_two_identical_numeric_offers_have_distinct_episode_ids(self):
        events = [Event("start", 42)]
        for seq, episode in [(1, "opaque-A"), (2, "opaque-B")]:
            events.extend([
                Event("frame", 42, seq=seq, context="OFFER_CANDIDATE", group=episode),
                Event("callback", 42, seq=seq, context="OFFER_CANDIDATE",
                      group=episode, guard_blocked=False, notified=True),
            ])
        events.append(Event("stop", 42))
        result = audit_stream(events)
        self.assertEqual([], result["violations"])
        self.assertEqual(2, result["counts"]["unique_labeled_offers"])
        self.assertEqual(2, result["counts"]["notifications"])

    def test_late_callback_after_stop_must_not_change_ui(self):
        events = [
            Event("start", 43), Event("frame", 43, seq=1),
            Event("stop", 43),
            Event("callback", 43, seq=1, context="OFFER_CANDIDATE",
                  group="opaque-C", ui_applied=True),
        ]
        result = audit_stream(events)
        self.assertIn("callback_after_stop_applied",
                      [error for _, error in result["violations"]])


if __name__ == "__main__":
    unittest.main()

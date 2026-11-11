"""Synthetic-only tests for concurrency and stale MediaProjection OCR callbacks."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stream_audit import Event as E, audit_stream


class TemporalSafetyTests(unittest.TestCase):
    def test_two_inferences_in_flight_are_a_violation(self):
        r = audit_stream([E("start", 5), E("frame", 5, 1),
                          E("inference_start", 5, 1), E("frame", 5, 2),
                          E("inference_start", 5, 2), E("inference_end", 5, 1),
                          E("inference_end", 5, 2)])
        self.assertIn("concurrent_inference", [v[1] for v in r["violations"]])
        self.assertEqual(r["counts"]["max_simultaneous_inferences"], 2)

    def test_serial_inferences_remain_valid(self):
        r = audit_stream([E("start", 5), E("frame", 5, 1),
                          E("inference_start", 5, 1), E("inference_end", 5, 1),
                          E("callback", 5, 1), E("frame", 5, 2),
                          E("inference_start", 5, 2), E("inference_end", 5, 2),
                          E("callback", 5, 2), E("stop", 5)])
        self.assertEqual(r["violations"], [])
        self.assertEqual(r["counts"]["max_simultaneous_inferences"], 1)

    def test_older_callback_cannot_overwrite_newer_results(self):
        r = audit_stream([E("start", 1), E("frame", 1, 1), E("frame", 1, 2),
                          E("callback", 1, 2, "OFFER_CANDIDATE", "new", ui_applied=True),
                          E("callback", 1, 1, "OFFER_CANDIDATE", "old", ui_applied=True)])
        self.assertIn("stale_callback_applied", [v[1] for v in r["violations"]])

    def test_discarding_older_callback_is_safe(self):
        r = audit_stream([E("start", 1), E("frame", 1, 1), E("frame", 1, 2),
                          E("callback", 1, 2, "OFFER_CANDIDATE", "new", ui_applied=True),
                          E("callback", 1, 1, "UNCERTAIN")])
        self.assertEqual(r["violations"], [])
        self.assertEqual(r["counts"]["stale_callbacks_suppressed"], 1)

    def test_callback_requires_a_frame_not_just_lower_sequence(self):
        r = audit_stream([E("start", 1), E("frame", 1, 1), E("frame", 1, 3),
                          E("callback", 1, 2)])
        self.assertIn("callback_without_frame", [v[1] for v in r["violations"]])

    def test_duplicate_callbacks_detected_without_notification(self):
        r = audit_stream([E("start", 1), E("frame", 1, 1),
                          E("callback", 1, 1), E("callback", 1, 1)])
        self.assertIn("duplicate_callback", [v[1] for v in r["violations"]])

    def test_late_callback_after_stop_restarted_session_is_discarded(self):
        r = audit_stream([E("start", 1), E("frame", 1, 0),
                          E("inference_start", 1, 0), E("stop", 1),
                          E("start", 2), E("frame", 2, 0),
                          E("callback", 1, 0, "OFFER_CANDIDATE", "old"),
                          E("callback", 2, 0, "OFFER_CANDIDATE", "new", ui_applied=True)])
        self.assertEqual(r["violations"], [])
        self.assertEqual(r["counts"]["late_or_foreign_events"], 1)
        self.assertEqual(r["counts"]["inferences_pending_at_stop"], 1)

    def test_unpaired_inference_end_is_a_violation(self):
        r = audit_stream([E("start", 1), E("frame", 1, 0), E("inference_end", 1, 0)])
        self.assertIn("inference_end_without_start", [v[1] for v in r["violations"]])

    def test_unknown_context_or_unlabeled_alert_is_a_violation(self):
        r = audit_stream([E("start", 1), E("frame", 1, 0),
                          E("callback", 1, 0, "OFFER_CANDIDATE", notified=True),
                          E("frame", 1, 1), E("callback", 1, 1, "OTHER", "A")])
        types = [v[1] for v in r["violations"]]
        self.assertIn("notification_without_offer_identity", types)
        self.assertIn("unknown_context", types)


if __name__ == "__main__":
    unittest.main()

"""Fixtures 100% fictícios, sem dados de corridas reais."""
import unittest
from stream_audit import Event as E, audit_stream

class StreamAuditTests(unittest.TestCase):
    def test_thirty_frames_one_offer(self):
        events = [E("start", 1)]
        for i in range(30):
            events.extend((E("frame", 1, i), E("callback", 1, i, "OFFER_CANDIDATE", "offer-A", notified=i==0)))
        events.append(E("stop", 1))
        result = audit_stream(events)
        self.assertEqual(result["counts"]["frames"], 30)
        self.assertEqual(result["counts"]["unique_labeled_offers"], 1)
        self.assertEqual(result["counts"]["notifications"], 1)
        self.assertEqual(result["violations"], [])

    def test_same_price_different_offers_not_collapsed(self):
        result = audit_stream([E("start", 1), E("frame",1,0), E("callback",1,0,"OFFER_CANDIDATE","A",notified=True), E("frame",1,1), E("callback",1,1,"OFFER_CANDIDATE","B",notified=True)])
        self.assertEqual(result["counts"]["unique_labeled_offers"], 2)

    def test_map_post_uncertain_never_notify(self):
        result = audit_stream([E("start", 1), E("frame",1,0), E("callback",1,0,"NON_OFFER",notified=True), E("frame",1,1), E("callback",1,1,"UNCERTAIN",notified=True)])
        self.assertEqual([v[1] for v in result["violations"]], ["notification_on_non_offer", "notification_on_uncertain"])

    def test_late_callback_and_history_detected(self):
        result = audit_stream([E("start",1), E("frame",1,0), E("stop",1), E("callback",1,0,"OFFER_CANDIDATE","A",notified=True,history_written=True)])
        self.assertIn("callback_after_stop_applied", [v[1] for v in result["violations"]])

    def test_financial_guard_and_duplicate_notification(self):
        result = audit_stream([E("start",1), E("frame",1,0), E("callback",1,0,"OFFER_CANDIDATE","A",notified=True,unsafe_financial=True,guard_blocked=False), E("frame",1,1), E("callback",1,1,"OFFER_CANDIDATE","A",notified=True)])
        names = [v[1] for v in result["violations"]]
        self.assertIn("unsafe_financial_unblocked", names)
        self.assertIn("duplicate_notification", names)

    def test_invalid_epoch_reuse_and_frame_sequence(self):
        result = audit_stream([E("start",1), E("frame",1,3), E("frame",1,3), E("stop",1), E("start",1)])
        self.assertEqual([v[1] for v in result["violations"]], ["nonmonotonic_frame","invalid_start"])

    def test_roi_cost_aggregate(self):
        result = audit_stream([E("start",1), E("frame",1,0), E("callback",1,0,"UNCERTAIN",inference_ms=125,roi_passes=4)])
        self.assertEqual(result["counts"]["roi_passes_total"],4)
        self.assertEqual(result["counts"]["inference_ms_total"],125)

if __name__ == "__main__":
    unittest.main()

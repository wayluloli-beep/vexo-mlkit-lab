"""Synthetic stream regressions. No screenshots, OCR strings or real routes."""
import unittest
from stream_audit import Event, audit_stream


def frame(epoch, seq, group="A", context="OFFER_CANDIDATE"):
    return Event("frame", epoch, seq, context=context, group=group)


def cb(epoch, seq, group="A", context="OFFER_CANDIDATE",
       notified=False, blocked=False, unsafe=False, ms=70, roi=0, ui=False):
    return Event("callback", epoch, seq, context=context, group=group,
                 notified=notified, guard_blocked=blocked,
                 unsafe_financial=unsafe, inference_ms=ms,
                 roi_passes=roi, ui_applied=ui)


class StreamTemporalRegressions(unittest.TestCase):
    def check(self, events, expected_offers, expected_notifications, violations=()):
        result = audit_stream(events)
        self.assertEqual(expected_offers, result["counts"].get("unique_labeled_offers", 0))
        self.assertEqual(expected_notifications, result["counts"].get("notifications", 0))
        self.assertEqual(list(violations), [v[1] for v in result["violations"]])
        return result["counts"]

    def test_thirty_frames_one_offer(self):
        events = [Event("start", 1)]
        for n in range(30):
            events.extend((frame(1, n), cb(1, n, notified=n == 1)))
        events.append(Event("stop", 1))
        counts = self.check(events, 1, 1)
        self.assertEqual(30, counts["frames"])
        self.assertEqual(30, counts["callbacks"])

    def test_same_price_different_visual_groups(self):
        # A and B have deliberately identical financial values outside the
        # event schema; distinct opaque visual groups must not be merged.
        events = [Event("start", 1), frame(1, 0, "A"),
                  cb(1, 0, "A", notified=True),
                  frame(1, 1, "", "NON_OFFER"),
                  cb(1, 1, "", "NON_OFFER"),
                  frame(1, 2, "B"), cb(1, 2, "B", notified=True)]
        self.check(events, 2, 2)

    def test_map_post_uncertain_no_alert(self):
        events = [Event("start", 1)]
        for n, context in enumerate(("NON_OFFER", "NON_OFFER", "UNCERTAIN")):
            events.extend((frame(1, n, "", context),
                           cb(1, n, "", context, blocked=True)))
        counts = self.check(events, 0, 0)
        self.assertEqual(3, counts["guard_abstentions"])

    def test_duplicate_notification_is_detected(self):
        events = [Event("start", 1), frame(1, 0),
                  cb(1, 0, notified=True), frame(1, 1),
                  cb(1, 1, notified=True)]
        self.check(events, 1, 1, ("duplicate_notification",))

    def test_stop_discards_old_callback(self):
        events = [Event("start", 1), frame(1, 0),
                  Event("inference_start", 1, 0), Event("stop", 1),
                  cb(1, 0), Event("start", 2), frame(2, 0, "B"),
                  cb(2, 0, "B", notified=True)]
        counts = self.check(events, 1, 1)
        self.assertEqual(1, counts["late_or_foreign_events"])
        self.assertEqual(1, counts["inferences_pending_at_stop"])

    def test_stop_late_callback_applied_is_violation(self):
        events = [Event("start", 1), frame(1, 0), Event("stop", 1),
                  cb(1, 0, notified=True, ui=True)]
        self.check(events, 0, 0, ("callback_after_stop_applied",))

    def test_stale_callback_must_not_modify_ui(self):
        events = [Event("start", 1), frame(1, 0), frame(1, 1),
                  cb(1, 1, notified=True), cb(1, 0, ui=True)]
        self.check(events, 1, 1, ("stale_callback_applied",))

    def test_financial_guard_abstains(self):
        events = [Event("start", 1), frame(1, 0),
                  cb(1, 0, blocked=True, unsafe=True)]
        counts = self.check(events, 1, 0)
        self.assertEqual(1, counts["guard_abstentions"])

    def test_unsafe_financial_without_guard_is_violation(self):
        events = [Event("start", 1), frame(1, 0),
                  cb(1, 0, unsafe=True)]
        self.check(events, 1, 0, ("unsafe_financial_unblocked",))

    def test_latency_roi_cost_synthetic_only(self):
        events = [Event("start", 1)]
        for n, (latency, roi) in enumerate(((80, 4), (120, 2), (200, 2))):
            events.extend((frame(1, n), cb(1, n, ms=latency, roi=roi)))
        counts = self.check(events, 1, 0)
        self.assertEqual(400, counts["inference_ms_total"])
        self.assertEqual(8, counts["roi_passes_total"])
        self.assertEqual(400 / 3, counts["inference_ms_total"] / counts["callbacks"])
        # Shared ROI hypothetical: 2 instead of 4 on first callback = 25% fewer total ROI passes.
        self.assertEqual(6, counts["roi_passes_total"] - 2)

    def test_roi_optimization_must_not_override_guard(self):
        # Fewer OCR passes cannot make an unsafe result safe.
        events = [Event("start", 1), frame(1, 0),
                  cb(1, 0, blocked=True, unsafe=True, roi=2)]
        self.check(events, 1, 0)


if __name__ == "__main__":
    unittest.main()

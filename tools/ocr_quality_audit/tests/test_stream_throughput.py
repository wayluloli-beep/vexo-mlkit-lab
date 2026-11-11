"""No private media or OCR payload: deterministic synthetic traces only."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stream_audit import Event as E
from stream_throughput import summarize_trace


class TemporalThroughputTests(unittest.TestCase):
    def test_thirty_frames_single_offer_one_alert_and_p95(self):
        events = [E("start", 1, at_ms=0)]
        for seq in range(30):
            t = 100 + seq * 100
            events.append(E("frame", 1, seq, "OFFER_CANDIDATE", "synthetic-A", at_ms=t))
            events.append(E("inference_start", 1, seq, at_ms=t + 10))
            events.append(E("inference_end", 1, seq, at_ms=t + 30))
            events.append(E("callback", 1, seq, "OFFER_CANDIDATE", "synthetic-A",
                            guard_blocked=False, notified=seq == 1, at_ms=t + 35,
                            roi_passes=2))
        events.append(E("stop", 1, at_ms=3100))
        r = summarize_trace(events)
        self.assertEqual(r["violations"], [])
        self.assertEqual((r["frames"], r["unique_offers"], r["notifications"]), (30, 1, 1))
        self.assertEqual(r["ocr_completed_timed"], 30)
        self.assertEqual(r["ocr_p95_ms"], 20)
        self.assertEqual(r["first_offer_alert_p50_ms"], 135)
        self.assertEqual(r["roi_passes"], 60)
        self.assertEqual(r["roi_passes_per_alert"], 60)

    def test_distinct_groups_even_with_identical_fictional_prices(self):
        events = [E("start", 2, at_ms=0)]
        for i, group in enumerate(("A", "B")):
            events += [E("frame", 2, i, "OFFER_CANDIDATE", group, at_ms=100 + i*100),
                       E("callback", 2, i, "OFFER_CANDIDATE", group,
                         guard_blocked=False, notified=True, at_ms=120 + i*100)]
        r = summarize_trace(events)
        self.assertEqual((r["unique_offers"], r["notifications"], r["offer_alerts_measured"]), (2, 2, 2))
        self.assertEqual(r["violations"], [])

    def test_nonoffer_uncertain_and_financial_abstention(self):
        events = [E("start", 3, at_ms=0)]
        for i, context in enumerate(("NON_OFFER", "UNCERTAIN", "OFFER_CANDIDATE")):
            events.append(E("frame", 3, i, context, "C" if i == 2 else "", at_ms=100*i))
            events.append(E("callback", 3, i, context, "C" if i == 2 else "",
                            unsafe_financial=i == 2, guard_blocked=True, at_ms=100*i+10))
        r = summarize_trace(events)
        self.assertEqual(r["notifications"], 0)
        self.assertEqual(r["offer_alerts_measured"], 0)
        self.assertIsNone(r["first_offer_alert_p95_ms"])
        self.assertEqual(r["violations"], [])

    def test_callback_after_stop_is_not_an_alert(self):
        events = [E("start", 4, at_ms=0), E("frame", 4, 0, at_ms=10),
                  E("inference_start", 4, 0, at_ms=15),
                  E("stop", 4, at_ms=20),
                  E("callback", 4, 0, "OFFER_CANDIDATE", "D", at_ms=50)]
        r = summarize_trace(events)
        self.assertEqual(r["pending_at_stop"], 1)
        self.assertEqual(r["notifications"], 0)
        self.assertEqual(r["violations"], [])

    def test_callback_after_stop_applied_is_violation(self):
        events = [E("start", 5, at_ms=0), E("frame", 5, 0, at_ms=10),
                  E("stop", 5, at_ms=20),
                  E("callback", 5, 0, "OFFER_CANDIDATE", "D",
                    notified=True, ui_applied=True, at_ms=50)]
        r = summarize_trace(events)
        self.assertIn("callback_after_stop_applied", [x[1] for x in r["violations"]])
        self.assertEqual(r["notifications"], 0)

    def test_empty_and_sparse_trace_do_not_invent_latency(self):
        r = summarize_trace([E("start", 6), E("stop", 6)])
        self.assertIsNone(r["ocr_p95_ms"])
        self.assertIsNone(r["frames_per_second"])
        self.assertIsNone(r["roi_passes_per_alert"])

if __name__ == "__main__":
    unittest.main()

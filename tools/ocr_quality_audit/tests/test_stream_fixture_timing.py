"""Purely synthetic fixtures for MediaProjection OCR timing and frame identity."""
import unittest
from dataclasses import asdict
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stream_audit import Event, audit_stream
from stream_fixtures import (repeated_offer, map_offer_map, equal_numbers_distinct_offers,
                             stopped_with_late_callback, all_scenarios, varying_first_detection_latencies)
from stream_timing import timing_metrics, _p95
from stream_check import audit_document, parse_events, StreamInputError


class SyntheticTimingTests(unittest.TestCase):
    def test_repeated_offer_one_alert_not_thirty(self):
        result = audit_stream(repeated_offer())
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["counts"]["frames"], 30)
        self.assertEqual(result["counts"]["unique_labeled_offers"], 1)
        self.assertEqual(result["counts"]["notifications"], 1)
        self.assertEqual(result["counts"]["inference_starts"], 3)

    def test_first_offer_latency(self):
        timing = timing_metrics(repeated_offer())
        self.assertEqual(timing["fixtureOffersWithTimedFirstFrame"], 1)
        self.assertEqual(timing["offersNeverDetectedInTrace"], 0)
        self.assertEqual(timing["firstCandidateLatencyP95Ms"], 120)
        self.assertEqual(timing["firstAlertLatencyP95Ms"], 1520)
        self.assertEqual(timing["ocrInferenceP95Ms"], 120)

    def test_map_offer_map_not_two_offers(self):
        result = audit_stream(map_offer_map())
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["counts"]["unique_labeled_offers"], 1)
        self.assertEqual(result["counts"]["notifications"], 1)
        self.assertEqual(result["counts"]["non_offer_callbacks"], 10)

    def test_distinct_offers_even_if_numerically_identical(self):
        result = audit_stream(equal_numbers_distinct_offers())
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["counts"]["unique_labeled_offers"], 2)
        self.assertEqual(result["counts"]["notifications"], 2)

    def test_callback_after_stop_only_fails_if_applied(self):
        good = audit_stream(stopped_with_late_callback(False))
        bad = audit_stream(stopped_with_late_callback(True))
        self.assertEqual(good["violations"], [])
        self.assertIn("callback_after_stop_applied", [name for _, name in bad["violations"]])

    def test_rate_limit_never_parallel(self):
        result = audit_stream(repeated_offer(frames=30))
        self.assertEqual(result["counts"]["max_simultaneous_inferences"], 1)
        self.assertEqual(result["violations"], [])

    def test_nearest_rank_p95(self):
        self.assertIsNone(_p95([]))
        self.assertEqual(_p95([10, 20, 30, 40, 50, 60, 70, 80, 90, 100]), 100)

    def test_no_timestamp_does_not_create_fake_zero_latency(self):
        result = timing_metrics([Event("start", 1),
                                 Event("frame", 1, 0, "OFFER_CANDIDATE", "A"),
                                 Event("callback", 1, 0, "OFFER_CANDIDATE", "A",
                                       notified=True)])
        self.assertIsNone(result["firstCandidateLatencyP95Ms"])
        self.assertEqual(result["fixtureOffersWithTimedFirstFrame"], 0)

    def test_timing_json_roundtrip(self):
        records = [asdict(e) for e in repeated_offer()]
        records = [{key: value for key, value in r.items() if value is not None}
                   for r in records]
        result = audit_document({"schema": "vexo-stream-events-v1", "events": records})
        self.assertEqual(result["violations"], [])
        self.assertEqual(result["timing"]["firstCandidateLatencyP95Ms"], 120)
        self.assertEqual(result["timing"]["firstAlertLatencyP95Ms"], 1520)

    def test_timing_type_must_be_nonnegative_integer(self):
        with self.assertRaises(StreamInputError):
            parse_events({"schema": "vexo-stream-events-v1", "events": [
                {"kind": "start", "epoch": 1, "at_ms": "100"}]})

    def test_non_offer_frame_cannot_be_misread_as_live_offer(self):
        from stream_fixtures import event
        trace = [event("start", t=0), event("frame", seq=0, t=100, context="NON_OFFER"),
                 event("callback", seq=0, t=160, context="OFFER_CANDIDATE",
                       group="invented", notified=True)]
        codes = [code for _, code in audit_stream(trace)["violations"]]
        self.assertIn("candidate_on_non_offer_fixture_frame", codes)

    def test_callback_cannot_swap_identity_from_labeled_fixture(self):
        from stream_fixtures import event
        trace = [event("start", t=0), event("frame", seq=0, t=100,
                         context="OFFER_CANDIDATE", group="fixture-A"),
                 event("callback", seq=0, t=160, context="OFFER_CANDIDATE",
                       group="fixture-B", notified=True)]
        self.assertIn("candidate_identity_mismatch",
                      [code for _, code in audit_stream(trace)["violations"]])

    def test_long_stable_offer_causes_duplicate_notification_after_25s(self):
        r = audit_stream(repeated_offer(frames=350))
        self.assertIn("duplicate_notification", [v[1] for v in r["violations"]])
        self.assertEqual(r["counts"]["unique_labeled_offers"], 1)
        self.assertEqual(r["counts"]["notifications"], 1)
        self.assertEqual(r["counts"]["notification_attempts"], 2)

    def test_p95_uses_multiple_labeled_offers(self):
        trace = varying_first_detection_latencies()
        self.assertEqual(audit_stream(trace)["violations"], [])
        m = timing_metrics(trace)
        self.assertEqual(m["fixtureOffersWithTimedFirstFrame"], 5)
        self.assertEqual(m["firstCandidateLatencyP95Ms"], 450)
        self.assertEqual(m["firstAlertLatencyP95Ms"], 450)

    def test_synthetic_scenario_count(self):
        self.assertEqual(len(all_scenarios()), 7)


if __name__ == "__main__":
    unittest.main()

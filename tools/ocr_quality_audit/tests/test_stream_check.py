"""Synthetic-only tests for strict MediaProjection event JSON, without private app data."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from stream_check import StreamInputError, audit_document, parse_events


class StreamCheckTests(unittest.TestCase):
    def fixture(self, events):
        return {"schema": "vexo-stream-events-v1", "events": events}

    def test_synthetic_trace_yields_aggregate_report(self):
        events = [{"kind": "start", "epoch": 1},
                  {"kind": "frame", "epoch": 1, "seq": 0},
                  {"kind": "inference_start", "epoch": 1, "seq": 0},
                  {"kind": "inference_end", "epoch": 1, "seq": 0},
                  {"kind": "callback", "epoch": 1, "seq": 0,
                   "context": "OFFER_CANDIDATE", "group": "fiction_A", "notified": True},
                  {"kind": "stop", "epoch": 1}]
        report = audit_document(self.fixture(events))
        self.assertEqual(report["violations"], [])
        self.assertEqual(report["counts"]["notifications"], 1)
        self.assertNotIn("fiction_A", str(report))

    def test_reject_raw_ocr_or_identifying_fields(self):
        with self.assertRaises(StreamInputError):
            parse_events(self.fixture([{"kind": "frame", "epoch": 1, "rawText": "private"}]))
        with self.assertRaises(StreamInputError):
            parse_events(self.fixture([{"kind": "callback", "epoch": 1,
                                        "group": "a b freeform location"}]))

    def test_reject_wrong_types_and_envelope(self):
        for event in ({"kind": "start", "epoch": True},
                      {"kind": "frame", "epoch": 0, "seq": "1"},
                      {"kind": "callback", "epoch": 1, "notified": 1},
                      {"kind": "callback", "epoch": 1, "context": "raw OCR"}):
            with self.subTest(event=event), self.assertRaises(StreamInputError):
                parse_events(self.fixture([event]))
        with self.assertRaises(StreamInputError):
            parse_events({"schema": "unknown", "events": []})

    def test_violations_are_returned_without_private_content(self):
        report = audit_document(self.fixture([{"kind": "start", "epoch": 1},
            {"kind": "frame", "epoch": 1, "seq": 0},
            {"kind": "stop", "epoch": 1},
            {"kind": "callback", "epoch": 1, "seq": 0,
             "context": "OFFER_CANDIDATE", "group": "fiction_B", "ui_applied": True}]))
        self.assertIn("callback_after_stop_applied", [e[1] for e in report["violations"]])
        self.assertNotIn("fiction_B", str(report))


if __name__ == "__main__":
    unittest.main()

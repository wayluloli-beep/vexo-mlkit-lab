"""Synthetic regression probes; no screenshots, OCR text or personal data."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from stale_frame_gate_audit import Event, classify, audit

class StaleFrameGateTests(unittest.TestCase):
    def test_successful_ocr_can_be_stale(self):
        self.assertEqual(classify(Event(0,100,5100)),"STALE")

    def test_30_second_window_is_not_ocr_latency(self):
        self.assertEqual(audit([Event(28000,29500,29620)])["ocrP50Ms"],120)

    def test_queue_wait_counts_toward_frame_age(self):
        self.assertEqual(classify(Event(0,2900,3100)),"STALE")

    def test_ttl_boundary_is_fresh(self):
        self.assertEqual(classify(Event(0,1000,3000)),"FRESH")

    def test_callback_at_stop_is_rejected(self):
        self.assertEqual(classify(Event(0,100,150,stopped_ms=150)),"AFTER_STOP")

    def test_callback_before_stop_can_be_fresh(self):
        self.assertEqual(classify(Event(0,100,149,stopped_ms=150)),"FRESH")

    def test_latency_and_freshness_are_separate(self):
        es=[Event(0,0,100),Event(1000,1000,1300),
            Event(2000,2000,6000),Event(3000,3000,8000)]
        r=audit(es)
        self.assertEqual((r["fresh"],r["stale"],r["afterStop"]),(2,2,0))
        self.assertEqual((r["ocrP50Ms"],r["ocrP95Ms"]),(300,5000))

    def test_three_completed_ocr_can_produce_zero_classifications(self):
        es=[Event(0,100,5100),Event(700,800,5800),Event(1400,1500,9000)]
        r=audit(es)
        self.assertEqual(r["completed"],3)
        self.assertEqual(r["classificationEligible"],0)

    def test_after_stop_is_distinct_from_stale(self):
        self.assertEqual(classify(Event(0,100,9000,stopped_ms=2000)),"AFTER_STOP")

    def test_invalid_monotonic_order_is_rejected(self):
        with self.assertRaises(ValueError):
            audit([Event(200,100,300)])

    def test_invalid_types_rejected(self):
        for e in (Event(True,1,2),Event(0,0,1,stopped_ms=-1)):
            with self.subTest(e=e),self.assertRaises(ValueError):
                classify(e)

    def test_empty_run_does_not_invent_latency(self):
        self.assertIsNone(audit([])["ocrP95Ms"])

if __name__=="__main__":
    unittest.main()

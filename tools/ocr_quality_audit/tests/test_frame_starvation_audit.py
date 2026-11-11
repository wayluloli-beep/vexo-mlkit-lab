"""Synthetic-only scheduling tests for static screen starvation and controls."""
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from frame_starvation_audit import replay_capture_frames


class FrameStarvationAuditTests(unittest.TestCase):
    def test_24_frames_before_slow_ocr_finishes_only_one_attempt(self):
        trace = [i * 100 for i in range(24)]
        r = replay_capture_frames(trace, ocr_ms=5000)
        self.assertEqual(r["framesInFixture"], 24)
        self.assertEqual(r["ocrStartsPossible"], 1)
        self.assertFalse(r["twoIndependentOcrStartsPossible"])

    def test_one_refresh_after_first_completion_allows_second_attempt(self):
        trace = [i * 100 for i in range(24)] + [5200]
        r = replay_capture_frames(trace, ocr_ms=5000)
        self.assertEqual(r["ocrStartsPossible"], 2)

    def test_rapid_ocr_still_rate_limited(self):
        r = replay_capture_frames([0, 500, 900, 1200, 1500], ocr_ms=100)
        self.assertEqual(r["ocrStartsPossible"], 2)
        self.assertEqual(r["framesSkippedByRateLimit"], 3)

    def test_two_starts_possible_on_exact_boundary(self):
        r = replay_capture_frames([0, 1400], ocr_ms=1400)
        self.assertEqual(r["ocrStartsPossible"], 2)

    def test_no_frames_is_not_a_recognition_failure(self):
        r = replay_capture_frames([], ocr_ms=1000)
        self.assertEqual(r["ocrStartsPossible"], 0)

    def test_invalid_or_regressing_clock_is_rejected(self):
        for frames in ([10, 9], [10, -1], [10, True]):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                replay_capture_frames(frames, ocr_ms=100)

    def test_invalid_duration_and_throttle_rejected(self):
        with self.assertRaises(ValueError):
            replay_capture_frames([0, 300], ocr_ms=-1)
        with self.assertRaises(ValueError):
            replay_capture_frames([0, 300], ocr_ms=100, minimum_interval_ms=0)


if __name__ == "__main__":
    unittest.main()

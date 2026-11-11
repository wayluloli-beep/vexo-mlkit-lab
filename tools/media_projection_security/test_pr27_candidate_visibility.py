"""Independent regression checks for PR #27's visible-result lifecycle.

Static source checks are evidence of control flow, not Android runtime proof.
Uses only synthetic state; never stores screenshots or OCR data.
"""
import unittest
from pathlib import Path
import os

# Optional PR27 checkout to verify actual source; on the auditor branch, the
# synthetic regression remains runnable independently of Android branch files.
ROOT = Path(os.environ.get("VEXO_PR27_ROOT", "")).resolve() if os.environ.get("VEXO_PR27_ROOT") else None
SERVICE = ROOT / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java" if ROOT else None
GATE = ROOT / "app/src/main/java/com/vexo/mlkitlab/OfferEpisodeGate.java" if ROOT else None

class Model:
    def __init__(self):
        self.alerted = False
        self.candidate = False
        self.matched = 0
    def observe(self):
        if self.alerted:
            return False
        self.matched += 1
        if self.matched >= 2:
            self.alerted = self.candidate = True
            return True
        return False
    def uncertain(self):
        self.candidate = False  # LiveCaptureState.clearCandidate
        if not self.alerted:
            self.matched = 0

class CandidateVisibilityRegression(unittest.TestCase):
    def test_regression_same_offer_after_uncertainty_is_not_restored(self):
        """Reproduces a UX safety regression: stale candidate cleared but not restored."""
        m = Model()
        self.assertFalse(m.observe())
        self.assertTrue(m.observe())
        self.assertTrue(m.candidate)
        m.uncertain()
        self.assertFalse(m.candidate)
        self.assertFalse(m.observe())
        self.assertFalse(m.candidate)
        self.assertTrue(m.alerted)

    def test_real_service_clears_candidate_on_uncertainty(self):
        if SERVICE is None or not SERVICE.is_file():
            self.skipTest("Set VEXO_PR27_ROOT to PR27 checkout for source check")
        source = SERVICE.read_text(encoding="utf-8")
        segment = source.split("private void markFrameUnusable(",1)[1].split("private void evaluate(",1)[0]
        self.assertIn("episodes.uncertain();", segment)
        self.assertIn("closed=true;", segment)
        self.assertIn("LiveCaptureState.clearCandidate();", segment)

    def test_real_gate_suppresses_republish_after_alert(self):
        if GATE is None or not GATE.is_file():
            self.skipTest("Set VEXO_PR27_ROOT to PR27 checkout for source check")
        source = GATE.read_text(encoding="utf-8")
        segment = source.split("boolean observe(",1)[1].split("void uncertain(",1)[0]
        self.assertIn("if(alerted)", segment)
        self.assertIn("return false;", segment)

if __name__ == "__main__":
    unittest.main()

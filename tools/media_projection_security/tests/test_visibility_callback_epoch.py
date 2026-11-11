"""Static regression: async MediaProjection callbacks must be epoch-guarded.

Read-only check against the actual Android service source from PR #30.
No screenshots, user data, or Android code changes.
"""
import re
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[2] / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"

class VisibilityCallbackSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SOURCE.is_file():
            raise unittest.SkipTest("Android source absent in isolated audit branch; run against checked-out PR #30 source")
        cls.source = SOURCE.read_text(encoding="utf-8")

    def test_visibility_callback_checks_epoch(self):
        m = re.search(r"onCapturedContentVisibilityChanged\(boolean visible\)\s*\{(?P<body>.*?)\n\s*\}\n\s*\}", self.source, re.S)
        self.assertIsNotNone(m, "MediaProjection visibility callback missing")
        body = m.group("body")
        self.assertRegex(body, r"epoch\.get\(\)\s*==\s*session|epoch\.get\(\)\s*!=\s*session|sessionAlive\(session\)",
                         "P1: stale callback can overwrite LiveCaptureState visibility after STOP")

    def test_visibility_callback_checks_stopping(self):
        m = re.search(r"onCapturedContentVisibilityChanged\(boolean visible\)\s*\{(?P<body>.*?)\n\s*\}\n\s*\}", self.source, re.S)
        self.assertIsNotNone(m)
        self.assertRegex(m.group("body"), r"stopping|sessionAlive\(session\)",
                         "P1: visibility callback must not mutate UI after shutdown")

if __name__ == "__main__":
    unittest.main()

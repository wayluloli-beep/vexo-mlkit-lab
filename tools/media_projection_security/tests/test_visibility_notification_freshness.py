"""Regression: hiding MediaProjection content must neutralize stale offer notification.
Only source and synthetic state; no real screen or passenger content.
"""
import unittest
from pathlib import Path

class NotificationModel:
    def __init__(self):
        self.active = True
        self.visible = True
        self.offer = False
        self.notification_offer = False

    def confirm(self):
        self.offer = True
        self.notification_offer = True

    def visibility_lost(self, refresh_notification):
        self.visible = False
        self.offer = False
        if refresh_notification:
            self.notification_offer = False

class VisibilityNotificationTests(unittest.TestCase):
    def test_stale_foreground_notification_counterexample(self):
        model = NotificationModel()
        model.confirm()
        model.visibility_lost(refresh_notification=False)
        self.assertFalse(model.offer)
        self.assertTrue(model.notification_offer,
                        "Old title can still say a possible offer is present")

    def test_expected_visibility_transition(self):
        model = NotificationModel()
        model.confirm()
        model.visibility_lost(refresh_notification=True)
        self.assertFalse(model.notification_offer)

    def test_current_android_source_if_available(self):
        root = Path(__file__).resolve().parents[3]
        path = root / "app/src/main/java/com/vexo/mlkitlab/LiveCaptureService.java"
        if not path.exists():
            self.skipTest("Android code is not on this isolated audit branch")
        source = path.read_text(encoding="utf-8")
        start = source.index("onCapturedContentVisibilityChanged(boolean visible)")
        end = source.index("},captureHandler);", start)
        callback = source[start:end]
        self.assertIn("LiveCaptureState.clearCandidate()", callback)
        self.assertIn("notification(false)", callback,
                      "P1: visibility=false must neutralize stale offer notification")

if __name__ == "__main__":
    unittest.main()

"""Synthetic ordering tests for MediaProjection Android foreground flow."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ordering_review import review_text

VALID = """
public final class LiveCaptureService extends Service {
 @Override public int onStartCommand(Intent intent,int flags,int startId) {
    if (Build.VERSION.SDK_INT >= 29) {
       startForeground(7,notification,FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
    } else {
       startForeground(7,notification);
    }
    initiate(resultCode,consent);
    return START_NOT_STICKY;
 }
 private void initiate(int resultCode, Intent consent) {
    projection=mgr.getMediaProjection(resultCode,consent);
    projection.registerCallback(new MediaProjection.Callback(){
        @Override public void onStop() { shutdown(); }
    },captureHandler);
    display=projection.createVirtualDisplay("test",w,h,dpi,0,surface,null,null);
 }
}
"""


def statuses(text):
    return {r["code"]: r["status"] for r in review_text(text)}


class OrderingTests(unittest.TestCase):
    def test_valid_ordering_passes(self):
        self.assertTrue(all(s == "PASS" for s in statuses(VALID).values()))

    def test_initiate_before_foreground_is_blocked(self):
        changed = VALID.replace(
            "    initiate(resultCode,consent);\n    return",
            "    initiate(resultCode,consent);\n    startForeground(7,notification);\n    return")
        self.assertEqual("FAIL", statuses(changed)["FOREGROUND_BEFORE_CAPTURE_START"])

    def test_no_foreground_is_blocked(self):
        changed = VALID.replace("startForeground", "notForeground")
        self.assertEqual("FAIL", statuses(changed)["FOREGROUND_BEFORE_CAPTURE_START"])

    def test_callback_after_display_is_blocked(self):
        token = '    display=projection.createVirtualDisplay("test",w,h,dpi,0,surface,null,null);\n'
        changed = VALID.replace(token, "")
        changed = changed.replace("    projection.registerCallback(",
                                  token + "    projection.registerCallback(")
        self.assertEqual("FAIL", statuses(changed)["CALLBACK_BEFORE_DISPLAY"])

    def test_projection_after_callback_is_blocked(self):
        changed = VALID.replace("    projection=mgr.getMediaProjection(resultCode,consent);\n", "")
        changed = changed.replace(
            "    projection.registerCallback(",
            "    projection.registerCallback(")
        changed = changed.replace(
            "    display=projection.createVirtualDisplay",
            "    projection=mgr.getMediaProjection(resultCode,consent);\n    display=projection.createVirtualDisplay")
        self.assertEqual("FAIL", statuses(changed)["GET_PROJECTION_BEFORE_CALLBACK"])

    def test_comments_cannot_fake_foreground_order(self):
        changed = VALID.replace("startForeground(", "notForeground(")
        changed = changed.replace(
            "    initiate(resultCode,consent);",
            "    // startForeground(7,notification);\n    initiate(resultCode,consent);")
        self.assertEqual("FAIL", statuses(changed)["FOREGROUND_BEFORE_CAPTURE_START"])

    def test_multiple_projection_callsites_are_blocked(self):
        changed = VALID.replace("    projection=mgr.getMediaProjection(resultCode,consent);",
                                "    projection=mgr.getMediaProjection(resultCode,consent);\n    mgr.getMediaProjection(resultCode,consent);")
        self.assertEqual("FAIL", statuses(changed)["GET_PROJECTION_BEFORE_CALLBACK"])


if __name__ == "__main__":
    unittest.main()

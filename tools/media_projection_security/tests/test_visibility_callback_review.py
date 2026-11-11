"""Source-only regression tests for stale MediaProjection visibility callbacks."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from visibility_callback_review import audit_text

GOOD = """
public class LiveCaptureService {
  private void invalidateStoppedSession(long session) {
    synchronized(sessionLock) {
      if(epoch.get()!=session) return;
      stopping=true;
      active=false;
      epoch.incrementAndGet();
      LiveCaptureState.end("STOP");
    }
  }
  @Override public void onCapturedContentVisibilityChanged(boolean visible) {
    synchronized(sessionLock) {
      if(epoch.get()!=session || !active || stopping) return;
      capturedVisible=visible;
      LiveCaptureState.capturedContentVisibility(visible);
    }
  }
}
"""

def status(src=GOOD):
    return {r["code"]:r["status"] for r in audit_text(src)}

class VisibilityCallbackEpochTests(unittest.TestCase):
    def test_locked_current_session_is_safe_by_source_contract(self):
        self.assertTrue(all(x=="PASS" for x in status().values()), status())

    def test_unguarded_visibility_callback_fails(self):
        s=GOOD.replace(
            "    synchronized(sessionLock) {\n      if(epoch.get()!=session || !active || stopping) return;\n      capturedVisible=visible;",
            "    capturedVisible=visible;"
        ).replace(
            "      LiveCaptureState.capturedContentVisibility(visible);\n    }\n  }",
            "    LiveCaptureState.capturedContentVisibility(visible);\n  }"
        )
        self.assertEqual("FAIL",status(s)["VISIBILITY_CALLBACK_EPOCH_STOP_LOCK"])

    def test_epoch_check_outside_lock_not_enough(self):
        s=GOOD.replace(
            "    synchronized(sessionLock) {\n      if(epoch.get()!=session || !active || stopping) return;",
            "    if(epoch.get()!=session || !active || stopping) return;\n    synchronized(sessionLock) {")
        self.assertEqual("FAIL",status(s)["VISIBILITY_CALLBACK_EPOCH_STOP_LOCK"])

    def test_guard_after_state_write_not_enough(self):
        s=GOOD.replace(
            "      if(epoch.get()!=session || !active || stopping) return;\n      capturedVisible=visible;",
            "      capturedVisible=visible;\n      if(epoch.get()!=session || !active || stopping) return;")
        self.assertEqual("FAIL",status(s)["VISIBILITY_CALLBACK_EPOCH_STOP_LOCK"])

    def test_state_ui_write_after_lock_fails(self):
        s=GOOD.replace(
            "      LiveCaptureState.capturedContentVisibility(visible);\n    }",
            "    }\n    LiveCaptureState.capturedContentVisibility(visible);")
        self.assertEqual("FAIL",status(s)["VISIBILITY_STATE_WRITES_IN_GUARDED_SECTION"])

    def test_stop_uses_same_lock_and_invalidates_generation(self):
        s=GOOD.replace("      epoch.incrementAndGet();","      // epoch bump removed")
        self.assertEqual("FAIL",status(s)["STOP_INVALIDATES_SAME_LOCK"])

    def test_stopping_guard_is_required(self):
        s=GOOD.replace("|| !active || stopping","|| !active")
        self.assertEqual("FAIL",status(s)["VISIBILITY_CALLBACK_EPOCH_STOP_LOCK"])

    def test_active_guard_is_required(self):
        s=GOOD.replace("|| !active || stopping","|| stopping")
        self.assertEqual("FAIL",status(s)["VISIBILITY_CALLBACK_EPOCH_STOP_LOCK"])

if __name__=="__main__":
    unittest.main()

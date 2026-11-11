"""Synthetic review of lock scope for offer notifications, never actual OCR."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from notification_review import review_text

SERVICE = """
public class LiveCaptureService {
 private void clearCandidateIfCurrent(long session) {
  synchronized(sessionLock) {
   if(sessionAlive(session)) {
    if(episodes.nonOffer()) {
     LiveCaptureState.clearCandidate();
     NotificationManager nm=getNotificationManager();
     if(nm!=null) nm.notify(NOTIFICATION_ID,notification(false));
    }
   }
  }
 }
 private void evaluate(String text,long session) {
  synchronized(sessionLock) {
   if(!sessionAlive(session)) return;
   if(!episodes.observe(fingerprint)) return;
   if(!sessionAlive(session)) return;
   LiveCaptureState.candidate("fictional");
   NotificationManager nm=getNotificationManager();
   if(nm!=null) nm.notify(NOTIFICATION_ID,notification(true));
  }
 }
 private void invalidateStoppedSession(long session) {
  synchronized(sessionLock) {
   if(epoch.get()!=session) return;
   stopping=true; active=false; capturedVisible=false;
   epoch.incrementAndGet();
   LiveCaptureState.end("Stopped");
  }
  main.post(this::shutdown);
 }
}
"""
STATE = """
public final class LiveCaptureState {
 static void clearCandidate() {
  if(!active) return;
  lastCandidate="";
  status="Waiting";
 }
}
"""


def failures(service=SERVICE, state=STATE):
    return {x["code"] for x in review_text(service,state) if x["status"] == "FAIL"}


class NotificationReviewTests(unittest.TestCase):
    def test_good_lock_contract_all_pass(self):
        self.assertFalse(failures())

    def test_clear_outside_lock_is_blocked(self):
        source = SERVICE.replace(
            "     LiveCaptureState.clearCandidate();",
            "     // removed candidate clear"
        ).replace(
            "  }\n }\n private void evaluate",
            "  }\n  LiveCaptureState.clearCandidate();\n }\n private void evaluate", 1
        )
        self.assertIn("CLEAR_NOTIFICATION_LOCKED_WITH_STOP", failures(source))

    def test_unlocked_offer_notify_is_blocked(self):
        source = SERVICE.replace(
            "   LiveCaptureState.candidate(\"fictional\");",
            "   // no candidate publication"
        ).replace(
            "  }\n }\n private void invalidateStoppedSession",
            "  }\n  LiveCaptureState.candidate(\"fictional\");\n }\n private void invalidateStoppedSession", 1
        )
        self.assertIn("OFFER_NOTIFICATION_LOCKED_WITH_STOP", failures(source))

    def test_stop_cleanup_before_epoch_invalidated_blocked(self):
        source = SERVICE.replace(
            "   epoch.incrementAndGet();\n   LiveCaptureState.end",
            "   LiveCaptureState.end"
        ).replace(
            "  main.post(this::shutdown);",
            "  main.post(this::shutdown);\n  epoch.incrementAndGet();"
        )
        self.assertIn("STOP_ENDS_STATE_BEFORE_ASYNC_CLEANUP", failures(source))

    def test_clearing_candidate_must_not_end_session(self):
        state = STATE.replace(
            '  lastCandidate="";',
            '  active=false;\n  lastCandidate="";'
        )
        self.assertIn("CANDIDATE_CLEAR_PRESERVES_CAPTURE_SESSION", failures(state=state))


if __name__ == "__main__":
    unittest.main()

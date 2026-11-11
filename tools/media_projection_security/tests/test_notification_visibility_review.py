"""Regressions: no stale 'possible offer' notification when capture hidden."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from notification_visibility_review import review_text

GOOD = """
class LiveCaptureService {
 private Notification notification(boolean offerDetected) {
  return b.setContentTitle(offerDetected?"Vexo: confira uma possível oferta":"Vexo: leitura de tela ativa").build();
 }
 @Override public void onCapturedContentVisibilityChanged(boolean visible) {
  synchronized(sessionLock) {
   if(!active || stopping || epoch.get()!=session) return;
   capturedVisible=visible;
   LiveCaptureState.capturedContentVisibility(visible);
   if(!visible) {
    episodes.uncertain();
    LiveCaptureState.clearCandidate();
    NotificationManager nm=(NotificationManager)getSystemService(NOTIFICATION_SERVICE);
    if(nm!=null) nm.notify(NOTIFICATION_ID,notification(false));
   }
  }
  if(visible) scheduleOverlaySearching(session);
  else scheduleOverlayHide();
 }
}
"""

def status(source=GOOD):
    return {x["code"]:x["status"] for x in review_text(source)}

class NotificationVisibilityTests(unittest.TestCase):
    def test_good_notification_reset_and_session_guard(self):
        self.assertTrue(all(x=="PASS" for x in status().values()),status())

    def test_clear_candidate_without_updating_os_notification_fails(self):
        s=GOOD.replace("if(nm!=null) nm.notify(NOTIFICATION_ID,notification(false));","")
        self.assertEqual("FAIL",status(s)["VISIBILITY_LOSS_RESETS_ONGOING_OFFER_NOTIFICATION"])

    def test_notification_true_on_hidden_screen_fails(self):
        s=GOOD.replace("notification(false)","notification(true)")
        self.assertEqual("FAIL",status(s)["VISIBILITY_LOSS_RESETS_ONGOING_OFFER_NOTIFICATION"])

    def test_notification_update_outside_hidden_branch_fails(self):
        s=GOOD.replace(
            "    if(nm!=null) nm.notify(NOTIFICATION_ID,notification(false));",
            ""
        ).replace(
            "  if(visible) scheduleOverlaySearching(session);",
            "  nm.notify(NOTIFICATION_ID,notification(false));\n"
            "  if(visible) scheduleOverlaySearching(session);"
        )
        self.assertEqual("FAIL",status(s)["VISIBILITY_LOSS_RESETS_ONGOING_OFFER_NOTIFICATION"])

    def test_hidden_without_candidate_clear_fails(self):
        s=GOOD.replace("LiveCaptureState.clearCandidate();","")
        self.assertEqual("FAIL",status(s)["VISIBILITY_LOSS_CLEARS_CANDIDATE"])

    def test_no_epoch_guard_fails(self):
        s=GOOD.replace("epoch.get()!=session","false")
        self.assertEqual("FAIL",status(s)["VISIBILITY_LOSS_SESSION_EPOCH_GUARDED"])

    def test_no_session_lock_fails(self):
        s=GOOD.replace("synchronized(sessionLock)","synchronized(otherLock)")
        self.assertEqual("FAIL",status(s)["VISIBILITY_LOSS_SESSION_EPOCH_GUARDED"])

if __name__=="__main__":
    unittest.main()

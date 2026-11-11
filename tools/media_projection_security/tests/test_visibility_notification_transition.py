"""Regression: when MediaProjection becomes invisible, foreground alert must
return to neutral while the session is alive. Synthetic code only, no media.
"""
import unittest

def inspect_callback(source):
    marker="onCapturedContentVisibilityChanged(boolean visible)"
    if marker not in source:
        return False
    callback=source.split(marker,1)[1].split("},captureHandler);",1)[0]
    invisible=callback.split("if(!visible)",1)
    if len(invisible)<2:
        return False
    # Notification update must be within the guarded session lock and
    # inside the !visible branch, not merely elsewhere in the file.
    segment=invisible[1].split("}",1)[0]
    return ("notification(false)" in segment and
            "synchronized(sessionLock)" in callback.split("if(!visible)",1)[0] and
            "epoch.get()!=session" in callback.split("if(!visible)",1)[0])

class VisibilityNotificationTransitionTest(unittest.TestCase):
    def test_safe_callback_updates_notification(self):
        source="""onCapturedContentVisibilityChanged(boolean visible) {
            synchronized(sessionLock) {
                if(!active || stopping || epoch.get()!=session) return;
                if(!visible) {
                    LiveCaptureState.clearCandidate();
                    nm.notify(NOTIFICATION_ID,notification(false));
                }
            }
        },captureHandler);"""
        self.assertTrue(inspect_callback(source))

    def test_stale_offer_notification_is_detected(self):
        source="""onCapturedContentVisibilityChanged(boolean visible) {
            synchronized(sessionLock) {
                if(!active || stopping || epoch.get()!=session) return;
                if(!visible) {
                    episodes.uncertain();
                    LiveCaptureState.clearCandidate();
                }
            }
            if(visible) scheduleOverlaySearching(session);
            else scheduleOverlayHide();
        },captureHandler);"""
        self.assertFalse(inspect_callback(source))

    def test_update_outside_guard_is_not_accepted(self):
        source="""onCapturedContentVisibilityChanged(boolean visible) {
            synchronized(sessionLock) {
                if(!active || stopping || epoch.get()!=session) return;
                if(!visible) {
                    LiveCaptureState.clearCandidate();
                }
            }
            nm.notify(NOTIFICATION_ID,notification(false));
        },captureHandler);"""
        self.assertFalse(inspect_callback(source))

    def test_update_without_epoch_guard_is_not_accepted(self):
        source="""onCapturedContentVisibilityChanged(boolean visible) {
            synchronized(sessionLock) {
                if(!visible) {
                    nm.notify(NOTIFICATION_ID,notification(false));
                }
            }
        },captureHandler);"""
        self.assertFalse(inspect_callback(source))

if __name__=="__main__":
    unittest.main()

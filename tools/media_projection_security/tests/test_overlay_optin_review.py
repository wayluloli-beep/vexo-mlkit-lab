"""Synthetic overlay permission, touch and lifecycle source regressions."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from overlay_optin_review import review_text

OVERLAY = """
class VexoOfferOverlay {
 static boolean optedIn(Context context) {
  return context.getSharedPreferences(PREFS,Context.MODE_PRIVATE).getBoolean(OPT_IN,false);
 }
 static boolean allowed(Context context) {
  return Build.VERSION.SDK_INT>=26 && optedIn(context)
          && Settings.canDrawOverlays(context);
 }
 boolean ensureWindow() {
  if(window!=null) return true;
  WindowManager.LayoutParams params=new WindowManager.LayoutParams(
    205,120,WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
    WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE |
    WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE |
    WindowManager.LayoutParams.FLAG_SECURE,
    PixelFormat.TRANSLUCENT);
  params.alpha=0.76f;
  wm.addView(root,params);
  return true;
 }
}
"""
ACTIVITY = """
class LiveCaptureActivity {
 void toggleOverlay() {
  if(VexoOfferOverlay.allowed(this)) {
   VexoOfferOverlay.setOptIn(this,false);
   Intent off=new Intent(this,LiveCaptureService.class);
   off.setAction(LiveCaptureService.ACTION_HIDE_OVERLAY);
   startService(off);
   return;
  }
 }
}
"""
SERVICE = """
class LiveCaptureService {
 void onStartCommand(Intent intent,int flags,int startId) {
  String action=intent.getAction();
  if(ACTION_HIDE_OVERLAY.equals(action)) {
   scheduleOverlayHide();
  }
 }
 void scheduleOverlayHide() {
  final long version=overlayGeneration.incrementAndGet();
  main.post(() -> {
   synchronized(sessionLock) {
    if(version!=overlayGeneration.get()) return;
    if(offerOverlay!=null) offerOverlay.hide();
   }
  });
 }
 void shutdown() {
  scheduleOverlayHide();
  synchronized(sessionLock) {
   stopping=true;active=false;epoch.incrementAndGet();
  }
 }
}
"""

def findings(overlay=OVERLAY,activity=ACTIVITY,service=SERVICE):
    return {x["code"]:x["status"] for x in
            review_text(overlay,activity,service)}

class OverlaySourceTests(unittest.TestCase):
    def test_positive_baseline(self):
        self.assertTrue(all(v=="PASS" for v in findings().values()),findings())

    def test_missing_permission_is_blocked(self):
        p=OVERLAY.replace("Settings.canDrawOverlays(context)","true")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_OPTIN_AND_SYSTEM_PERMISSION"])

    def test_default_on_is_blocked(self):
        p=OVERLAY.replace("getBoolean(OPT_IN,false)","getBoolean(OPT_IN,true)")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_OPTIN_AND_SYSTEM_PERMISSION"])

    def test_touchable_overlay_is_blocked(self):
        p=OVERLAY.replace("FLAG_NOT_TOUCHABLE","FLAG_NOT_TOUCH_MODAL")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_DISPLAY_FLAGS"])

    def test_focusable_overlay_is_blocked(self):
        p=OVERLAY.replace("FLAG_NOT_FOCUSABLE","FLAG_WATCH_OUTSIDE_TOUCH")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_DISPLAY_FLAGS"])

    def test_secure_removed_is_blocked(self):
        p=OVERLAY.replace("FLAG_SECURE","FLAG_LAYOUT_IN_SCREEN")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_DISPLAY_FLAGS"])

    def test_alpha_above_android_limit_is_blocked(self):
        p=OVERLAY.replace("params.alpha=0.76f","params.alpha=0.92f")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_ANDROID12_ALPHA_LIMIT"])

    def test_alpha_equal_default_threshold(self):
        p=OVERLAY.replace("params.alpha=0.76f","params.alpha=0.8f")
        self.assertEqual("PASS",findings(overlay=p)["OVERLAY_ANDROID12_ALPHA_LIMIT"])

    def test_old_hide_without_version_check_is_blocked(self):
        p=SERVICE.replace("if(version!=overlayGeneration.get()) return;","")
        self.assertEqual("FAIL",findings(service=p)["OVERLAY_HIDE_GENERATION_GUARD"])

    def test_hide_without_lock_is_blocked(self):
        p=SERVICE.replace("synchronized(sessionLock)","while(true)",1)
        self.assertEqual("FAIL",findings(service=p)["OVERLAY_HIDE_GENERATION_GUARD"])

    def test_optout_without_service_hide_is_blocked(self):
        p=ACTIVITY.replace("startService(off);","")
        self.assertEqual("FAIL",findings(activity=p)["OVERLAY_OPTOUT_REMOVES_NOW"])

    def test_stop_without_hiding_is_blocked(self):
        p=SERVICE.replace("void shutdown() {\n  scheduleOverlayHide();",
                          "void shutdown() {")
        self.assertEqual("FAIL",findings(service=p)["OVERLAY_STOP_INVALIDATES_AND_HIDES"])

    def test_automated_click_is_blocked(self):
        p=OVERLAY.replace("wm.addView(root,params);","wm.addView(root,params);root.performClick();")
        self.assertEqual("FAIL",findings(overlay=p)["OVERLAY_NO_AUTOMATIC_CLICKS"])

if __name__=="__main__":
    unittest.main()

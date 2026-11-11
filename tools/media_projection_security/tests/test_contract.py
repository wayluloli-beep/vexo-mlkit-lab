"""Synthetic contract fixtures only: no real offer text, pixels, or passenger data."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_contract import audit, main

MANIFEST = """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
 <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
 <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION"/>
 <application>
  <activity android:name="com.vexo.mlkitlab.LiveCaptureActivity" android:exported="false"/>
  <service android:name="com.vexo.mlkitlab.LiveCaptureService"
           android:foregroundServiceType="mediaProjection" android:exported="false"/>
 </application>
</manifest>
"""

ACTIVITY = """
package com.vexo.mlkitlab;
import android.media.projection.MediaProjectionManager;
public class LiveCaptureActivity extends Activity {
 void start(){ startActivityForResult(manager.createScreenCaptureIntent(),401);
   Intent i=new Intent(this,LiveCaptureService.class); }
}
"""

SERVICE = """
package com.vexo.mlkitlab;
public class LiveCaptureService extends Service {
 void start() {
  startForeground(7, notification);
  projection=manager.getMediaProjection(resultCode,data);
  projection.registerCallback(new MediaProjection.Callback(){
    public void onStop(){ cleanup(); }
  }, handler);
  reader=ImageReader.newInstance(width,height,format,3);
  virtualDisplay=projection.createVirtualDisplay("Vexo",width,height,dpi,flags,reader.getSurface(),null,null);
 }
 void frame() {
  Image image=reader.acquireLatestImage();
  try { if (image!=null) analyze(image); }
  finally { if (image!=null) image.close(); }
 }
 void cleanup() { virtualDisplay.release(); reader.close(); }
}
"""


def create_fixture(root: Path, manifest: str = MANIFEST,
                   activity: str = ACTIVITY, service: str | None = SERVICE) -> None:
    m = root / "app/src/main/AndroidManifest.xml"
    m.parent.mkdir(parents=True, exist_ok=True)
    m.write_text(manifest, encoding="utf-8")
    j = root / "app/src/main/java/com/vexo/mlkitlab"
    j.mkdir(parents=True, exist_ok=True)
    (j / "LiveCaptureActivity.java").write_text(activity, encoding="utf-8")
    if service is not None:
        (j / "LiveCaptureService.java").write_text(service, encoding="utf-8")


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def statuses(self) -> dict[str, str]:
        return {x["code"]: x["status"] for x in audit(self.root)}

    def test_no_capture_in_main_is_explicit_skip(self):
        self.assertEqual(self.statuses()["CAPTURE_IMPLEMENTATION_PRESENT"], "SKIP")
        self.assertEqual(main(["--root", str(self.root)]), 0)

    def test_missing_capture_fails_when_required(self):
        self.assertEqual(audit(self.root, require_capture=True)[0]["status"], "FAIL")

    def test_safe_synthetic_service_passes_static_checks(self):
        create_fixture(self.root)
        self.assertEqual([x for x in audit(self.root) if x["status"] == "FAIL"], [])

    def test_missing_service_source_detected(self):
        create_fixture(self.root, service=None)
        results = self.statuses()
        self.assertEqual(results["CAPTURE_SERVICE_SOURCE"], "FAIL")
        self.assertEqual(results["STOP_CALLBACK_REGISTERED"], "FAIL")

    def test_missing_fgs_permission_detected(self):
        create_fixture(self.root, manifest=MANIFEST.replace(
            '<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PROJECTION"/>', ""))
        self.assertEqual(self.statuses()["FGS_REQUIRED_PERMISSIONS"], "FAIL")

    def test_exported_service_detected(self):
        create_fixture(self.root, manifest=MANIFEST.replace(
            'android:foregroundServiceType="mediaProjection" android:exported="false"',
            'android:foregroundServiceType="mediaProjection" android:exported="true"'))
        self.assertEqual(self.statuses()["CAPTURE_SERVICE_MANIFEST"], "FAIL")

    def test_activity_missing_from_manifest_detected(self):
        create_fixture(self.root, manifest=MANIFEST.replace(
            '<activity android:name="com.vexo.mlkitlab.LiveCaptureActivity" android:exported="false"/>', ""))
        self.assertEqual(self.statuses()["CAPTURE_ACTIVITY_MANIFEST"], "FAIL")

    def test_repeated_display_callsite_detected(self):
        create_fixture(self.root, service=SERVICE.replace(
            'virtualDisplay=projection.createVirtualDisplay(', 
            'other=projection.createVirtualDisplay("duplicate",1,1,1,0,null,null,null); virtualDisplay=projection.createVirtualDisplay('))
        self.assertEqual(self.statuses()["SINGLE_PROJECTION_AND_DISPLAY_CALLSITE"], "FAIL")

    def test_missing_stop_callback_detected(self):
        create_fixture(self.root, service=SERVICE.replace("public void onStop(){ cleanup(); }",
                                                              "public void onEnd(){ cleanup(); }"))
        self.assertEqual(self.statuses()["STOP_CALLBACK_REGISTERED"], "FAIL")

    def test_image_close_missing_detected(self):
        create_fixture(self.root, service=SERVICE.replace("image.close();", "discard(image);"))
        self.assertEqual(self.statuses()["IMAGE_CLOSE_FINALLY"], "FAIL")

    def test_file_output_in_capture_path_is_blocked(self):
        create_fixture(self.root, service=SERVICE + "\nclass Unsafe { FileOutputStream privateCapture; }")
        self.assertEqual(self.statuses()["NO_CAPTURE_PERSISTENCE_OR_EXFIL_CALLS"], "FAIL")

    def test_boot_receiver_rejected(self):
        extra = """<receiver android:name=".BootReceiver" android:exported="false">
         <intent-filter><action android:name="android.intent.action.BOOT_COMPLETED"/></intent-filter>
         </receiver>"""
        create_fixture(self.root, manifest=MANIFEST.replace("</application>",extra+"</application>"))
        self.assertEqual(self.statuses()["NO_BOOT_AUTOSTART"], "FAIL")

    def test_accessibility_service_rejected(self):
        create_fixture(self.root, manifest=MANIFEST.replace(
            "<application>", '<uses-permission android:name="android.permission.BIND_ACCESSIBILITY_SERVICE"/><application>'))
        self.assertEqual(self.statuses()["NO_ACCESSIBILITY_PERMISSION"], "FAIL")

    def test_secure_flag_bypass_rejected(self):
        create_fixture(self.root, service=SERVICE + "\nclass Unsafe { int mask=FLAG_SECURE ^ 1; }")
        self.assertEqual(self.statuses()["NO_CAPTURE_PERSISTENCE_OR_EXFIL_CALLS"], "FAIL")


if __name__ == "__main__":
    unittest.main()

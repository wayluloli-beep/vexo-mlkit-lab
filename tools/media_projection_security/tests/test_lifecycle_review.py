"""Synthetic source-level lifecycle risk checks; no real Android frames."""
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lifecycle_review import block, main, review_text

SERVICE_BASE = """
public class LiveCaptureService {
  void register() {
    projection.registerCallback(new MediaProjection.Callback() {
      @Override public void onStop() {
        main.post(() -> shutdown());
      }
    }, captureHandler);
  }
  private void resize(long epoch, int w, int h) {
    if (!active) return;
    try {
      ImageReader replacement=ImageReader.newInstance(w,h,1,3);
      virtualDisplay.resize(w,h,densityDpi);
      virtualDisplay.setSurface(replacement.getSurface());
      ImageReader old=imageReader;
      imageReader=replacement;
      if(old!=null) old.close();
    } catch(Exception ex) {
      main.post(() -> shutdown());
    }
  }
}
"""


def statuses(src: str) -> dict[str, str]:
    return {x["code"]: x["status"] for x in review_text(src)}


class LifecycleReviewTests(unittest.TestCase):
    def test_current_delayed_onstop_flagged(self):
        self.assertEqual(statuses(SERVICE_BASE)["STOP_INVALIDATES_EPOCH_BEFORE_DISPATCH"], "FAIL")

    def test_sync_epoch_increment_before_post_accepted(self):
        fixed = SERVICE_BASE.replace("main.post(() -> shutdown());",
                                     "epoch.incrementAndGet(); main.post(() -> shutdown());", 1)
        self.assertEqual(statuses(fixed)["STOP_INVALIDATES_EPOCH_BEFORE_DISPATCH"], "PASS")

    def test_sync_invalidation_only_after_post_not_accepted(self):
        fixed = SERVICE_BASE.replace("main.post(() -> shutdown());",
                                     "main.post(() -> shutdown()); epoch.incrementAndGet();", 1)
        self.assertEqual(statuses(fixed)["STOP_INVALIDATES_EPOCH_BEFORE_DISPATCH"], "FAIL")

    def test_current_resize_leak_flagged(self):
        self.assertEqual(statuses(SERVICE_BASE)["RESIZE_REPLACEMENT_RELEASE_ON_EXCEPTION"], "FAIL")

    def test_cleanup_of_replacement_in_catch_accepted(self):
        fixed = SERVICE_BASE.replace(
            "} catch(Exception ex) {\n      main.post(() -> shutdown());",
            "} catch(Exception ex) {\n      if(replacement!=null) replacement.close();\n      main.post(() -> shutdown());")
        self.assertEqual(statuses(fixed)["RESIZE_REPLACEMENT_RELEASE_ON_EXCEPTION"], "PASS")

    def test_missing_resize_requires_manual_review(self):
        idx = SERVICE_BASE.index("  private void resize(")
        fixed = SERVICE_BASE[:idx] + "}"
        self.assertEqual(statuses(fixed)["RESIZE_HANDLER_PRESENT"], "FAIL")

    def test_method_block_handles_nested_braces_and_strings(self):
        src = 'void onStop(){ String s="{a}"; if(active) { foo(); } main.post(() -> shutdown()); }'
        self.assertIn("main.post(", block(src, "onStop"))

    def test_no_android_service_skips_on_audit_only_branch(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(main(["--root", root]), 0)

    def test_required_android_service_missing_fails(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(main(["--root", root, "--require-service"]), 1)


if __name__ == "__main__":
    unittest.main()

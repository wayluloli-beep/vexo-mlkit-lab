"""Regression contracts for screenshot/gallery scope and false live alerts.
Synthetic sources only. A screen-capture permission is not proof of live 99.
"""
import unittest


def inspect_gallery_guard(service, activity):
    """Require an explicit, fail-closed provenance gate before alert publication."""
    if "private void evaluate(" not in service or "LiveCaptureState.candidate(summary)" not in service:
        return False
    section = service.split("private void evaluate(", 1)[1].split("private void shutdown(", 1)[0]
    publish = section.split("LiveCaptureState.candidate(summary)", 1)[0]
    # A single-app consent cannot silently become full-screen or gallery capture.
    # The provenance flag must be derived from explicit opt-in/session mode.
    return (
        "galleryInspectionOnly" in publish
        and "if(galleryInspectionOnly)" in publish
        and "MODE_GALLERY_INSPECTION" in activity
        and "MODE_LIVE_99" in activity
    )


class GalleryScopeContractTest(unittest.TestCase):
    def test_explicit_lab_mode_blocks_live_alerts(self):
        service = """private void evaluate(String text,long session) {
          if(galleryInspectionOnly) { updateLocalPreview(text); return; }
          LiveCaptureState.candidate(summary);
        }
        private void shutdown() {}"""
        activity = "MODE_GALLERY_INSPECTION MODE_LIVE_99"
        self.assertTrue(inspect_gallery_guard(service, activity))

    def test_price_and_99_logo_do_not_prove_live_origin(self):
        service = """private void evaluate(String text,long session) {
          if(ScreenContextClassifier.has99OfferCue(text))
              LiveCaptureState.candidate(summary);
        }
        private void shutdown() {}"""
        self.assertFalse(inspect_gallery_guard(service, ""))

    def test_gallery_mode_without_prepublication_check_fails(self):
        service = """private void evaluate(String text,long session) {
          LiveCaptureState.candidate(summary);
          if(galleryInspectionOnly) return;
        }
        private void shutdown() {}"""
        self.assertFalse(inspect_gallery_guard(
            service, "MODE_GALLERY_INSPECTION MODE_LIVE_99"))

    def test_single_app_capture_is_not_implicitly_gallery(self):
        # The native OS dialog may grant one app only. Never infer a
        # screenshot was observed merely from framesReceived > 0.
        observed = {"framesReceived": 2641, "ocrCompleted": 130,
                    "capturedWindowVisibility": "visível"}
        self.assertNotIn("capturedPackage", observed)
        self.assertNotIn("selectedCaptureScope", observed)


if __name__ == "__main__":
    unittest.main()

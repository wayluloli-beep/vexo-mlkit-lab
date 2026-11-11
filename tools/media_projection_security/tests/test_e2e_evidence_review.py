"""Synthetic tests for reviewer of PR26 E2E evidence, not real device tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from e2e_evidence_review import review_text

GOOD = """
public final class LiveProjectionConsentE2eTest {
 private static void approveThroughSystemDialog(UiDevice device) {
     UiObject2 entire=awaitAny(device,"Entire screen");
     assertNotNull(entire);
     entire.click();
     UiObject2 start=awaitAny(device,"Start now");
     start.click();
 }
 @Test public void nativeConsentThenFakeOfferProducesRealFramesAndStops() {
     UiDevice device=UiDevice.getInstance(instrumentation);
     Intent launch=new Intent(context,LiveCaptureActivity.class);
     approveThroughSystemDialog(device);
     Intent demo=new Intent(context,DemoOfferActivity.class);
     long[] n=LiveCaptureState.counts();
     assertTrue("frames "+n[0],n[0]>=2);
     assertTrue("ocr "+n[1],n[1]>=2);
     assertTrue("avisos "+n[2],n[2]>=1);
 }
 @Test public void stopRegardlessOfOcr() {
     Intent stop=new Intent(context,LiveCaptureService.class)
         .setAction(LiveCaptureService.ACTION_STOP);
     assertTrue(LiveCaptureState.snapshot().startsWith("SEM CAPTURA:"));
 }
}
"""


def statuses(source):
    return {c["code"]: c["status"] for c in review_text(source)}


class EvidenceReviewTests(unittest.TestCase):
    def test_staged_native_e2e_contract_passes(self):
        self.assertTrue(all(x == "PASS" for x in statuses(GOOD).values()))

    def test_optional_screen_scope_is_not_evidence(self):
        bad = GOOD.replace("entire.click();", "if(dropdown!=null) entire.click();")
        self.assertEqual(statuses(bad)["E2E_SCOPE_EXPLICIT"], "FAIL")

    def test_mock_consent_without_uiautomator_is_blocked(self):
        bad = GOOD.replace("UiDevice.getInstance", "FakeConsentDevice.getInstance")
        self.assertEqual(statuses(bad)["E2E_USES_NATIVE_UI_CONSENT"], "FAIL")

    def test_missing_real_capture_metrics_are_blocked(self):
        bad = GOOD.replace("LiveCaptureState.counts()", "FakeCounter.counts()")
        self.assertEqual(statuses(bad)["E2E_EXERCISES_SYNTHETIC_DEMO"], "FAIL")

    def test_combined_awaitcounts_is_not_staged_diagnosis(self):
        bad = GOOD.replace(
            'assertTrue("frames "+n[0],n[0]>=2);\n     assertTrue("ocr "+n[1],n[1]>=2);\n     assertTrue("avisos "+n[2],n[2]>=1);',
            'assertTrue("no combined metrics",awaitCounts(2,2,1,30000));'
        )
        self.assertEqual(statuses(bad)["E2E_STAGEWISE_ASSERTIONS"], "FAIL")

    def test_ocr_failure_cannot_skip_only_stop_assertion(self):
        bad = GOOD.replace(
            " @Test public void stopRegardlessOfOcr() {",
            " private void stopRegardlessOfOcr() {"
        )
        self.assertEqual(statuses(bad)["E2E_STOP_NOT_SKIPPED_BY_OCR_FAILURE"], "FAIL")

    def test_screen_dump_is_rejected(self):
        bad = GOOD.replace("long[] n=LiveCaptureState.counts();",
                           "device.takeScreenshot(file);\n     long[] n=LiveCaptureState.counts();")
        self.assertEqual(statuses(bad)["E2E_NO_PRIVATE_SCREEN_DUMPS"], "FAIL")

    def test_missing_demo_activity_is_blocked(self):
        bad = GOOD.replace("DemoOfferActivity.class", "UnknownUserApp.class")
        self.assertEqual(statuses(bad)["E2E_EXERCISES_SYNTHETIC_DEMO"], "FAIL")


if __name__ == "__main__":
    unittest.main()

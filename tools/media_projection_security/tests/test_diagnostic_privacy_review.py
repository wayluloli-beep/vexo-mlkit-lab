"""Synthetic contracts for privacy-safe diagnostic export and OCR timing."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnostic_privacy_review import SAFE_VALUES, BASE_FIELDS, review_text

REPORT_VALUES = "\n".join(
    f'    report.put("{key}", {value});'
    for key, value in SAFE_VALUES.items()
)

STATE = (
    "public class LiveCaptureState {\n"
    "static synchronized void begin() { latency.reset(); }\n"
    "static synchronized String safeDiagnosticReport() {\n"
    " JSONObject report=new JSONObject();\n" + REPORT_VALUES + "\n"
    " return report.toString(2);\n"
    "}\n"
    "}\n"
)
ACTIVITY = """
public final class LiveCaptureActivity {
 void onCreate() {
  Button copyReport=new Button(this);
  copyReport.setText("Copiar diagnóstico da captura para análise");
  copyReport.setOnClickListener(v -> {
   ClipboardManager clipboard=(ClipboardManager)
     getSystemService(Context.CLIPBOARD_SERVICE);
   clipboard.setPrimaryClip(ClipData.newPlainText(
      "Diagnóstico Vexo",LiveCaptureState.safeDiagnosticReport()));
  });
 }
}
"""
SERVICE = """
public final class LiveCaptureService {
 void process() {
  if(active && !stopping && epoch.get()==session) {
    LiveCaptureState.ocrLatency(
      Math.max(0,SystemClock.elapsedRealtime()-startedAt));
  }
 }
}
"""
LATENCY = """
public final class CaptureLatencyStats {
 private static final int MAX_SAMPLES=128;
 void record(long elapsedMs) {
  if(elapsedMs<0 || elapsedMs>600000) return;
 }
 long[] snapshot() {
   long[] sorted=Arrays.copyOf(recentMs,count);
   return sorted;
 }
}
"""


def by_code(state=STATE, activity=ACTIVITY, service=SERVICE, latency=LATENCY,
            require_latency=False):
    return {c["code"]: c["status"]
            for c in review_text(state, activity, service, latency,
                                 require_latency=require_latency)}


class DiagnosticPrivacyReviewTest(unittest.TestCase):
    def test_allowlisted_user_initiated_report_passes(self):
        self.assertTrue(all(status == "PASS" for status in by_code().values()))

    def test_new_field_fails_closed(self):
        bad = STATE.replace(
            " return report.toString(2);",
            ' report.put("passengerAddress", "fictitious");\n return report.toString(2);'
        )
        self.assertEqual("FAIL", by_code(state=bad)["EXPORT_SCHEMA_FIELD_ALLOWLIST"])

    def test_dangerous_value_even_under_known_key_fails(self):
        bad = STATE.replace(
            'report.put("framesReceived", n[0])',
            'report.put("framesReceived", lastCandidate)')
        self.assertEqual("FAIL", by_code(state=bad)["EXPORT_VALUES_ALLOWLIST"])

    def test_raw_candidate_reference_is_rejected(self):
        bad = STATE.replace(
            " return report.toString(2);",
            " String leaked=lastCandidate;\n return report.toString(2);"
        )
        self.assertEqual("FAIL", by_code(state=bad)["EXPORT_NO_RAW_SCREEN_REFERENCE"])

    def test_duplicate_key_rejected(self):
        bad = STATE.replace(
            " return report.toString(2);",
            ' report.put("schema","vexo-live-capture-diagnostic-v1");\n return report.toString(2);'
        )
        self.assertEqual("FAIL", by_code(state=bad)["EXPORT_SCHEMA_FIELD_ALLOWLIST"])

    def test_automatic_clipboard_copy_does_not_pass(self):
        bad = ACTIVITY.replace("copyReport.setOnClickListener(v -> {",
                               "/* handler removed */")
        self.assertEqual("FAIL", by_code(activity=bad)["CLIPBOARD_EXPLICIT_USER_CLICK"])

    def test_second_clipboard_copy_automatically_detected(self):
        bad = ACTIVITY.replace(
            " void onCreate() {",
            " void onResume() { clipboard.setPrimaryClip(other); }\n void onCreate() {"
        )
        self.assertEqual("FAIL", by_code(activity=bad)["CLIPBOARD_EXPLICIT_USER_CLICK"])

    def test_latency_without_epoch_guard_is_rejected(self):
        bad = SERVICE.replace(
            "if(active && !stopping && epoch.get()==session)",
            "if(active)")
        self.assertEqual("FAIL", by_code(service=bad)["OCR_LATENCY_CURRENT_SESSION_GUARD"])

    def test_latency_without_reset_is_rejected(self):
        bad = STATE.replace("latency.reset();", "")
        self.assertEqual("FAIL", by_code(state=bad)["OCR_LATENCY_CURRENT_SESSION_GUARD"])

    def test_unbounded_sample_window_is_rejected(self):
        bad = LATENCY.replace("MAX_SAMPLES=128", "MAX_SAMPLES=200000")
        self.assertEqual("FAIL", by_code(latency=bad)["OCR_LATENCY_BOUNDED_SAMPLE_WINDOW"])

    def test_missing_latency_source_stays_unverified(self):
        self.assertEqual("SKIP", by_code(latency=None)["OCR_LATENCY_BOUNDED_SAMPLE_WINDOW"])

    def test_required_latency_source_missing_fails(self):
        self.assertEqual("FAIL", by_code(latency=None,require_latency=True)["OCR_LATENCY_BOUNDED_SAMPLE_WINDOW"])

    def test_original_clipboard_report_without_latency_is_supported(self):
        body = "\\n".join(f'report.put("{k}", {v});' for k,v in SAFE_VALUES.items() if k in BASE_FIELDS)
        old = STATE.replace(REPORT_VALUES, body)
        checks = by_code(state=old,latency=None)
        self.assertEqual("PASS", checks["EXPORT_SCHEMA_FIELD_ALLOWLIST"])
        self.assertEqual("SKIP", checks["OCR_LATENCY_BOUNDED_SAMPLE_WINDOW"])


if __name__ == "__main__":
    unittest.main()
